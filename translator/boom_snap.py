"""BOOM 风格吸附层。

把翻译候选拿到 BOOM 全库（glossary/boom_style_index.sqlite）比对词频：
- 候选已是 BOOM 常见写法           -> 保留
- 候选不常见，但有更常见的「形变体」  -> 吸附（flame thrower -> flamethrower）
- 候选不常见，但对齐表里有更常见的
  「同义 BOOM 写法」且符合中文输入     -> 吸附（用户核心诉求：进 BOOM 比对替换）
- 否则                              -> 保留模型/词典输出

只读 BOOM 索引，不写入。
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from rapidfuzz import fuzz

from translator import align

from translator.paths import BOOM_INDEX_PATH

# 阈值（可在验收中迭代）
PHRASE_COMMON = 5      # 多词短语视为「BOOM 常见」的频次
TOKEN_COMMON = 20      # 单词视为「BOOM 常见」的频次
FORM_SIM = 88.0        # 形变体最低相似度（rapidfuzz ratio）
VARIANT_MIN = 3        # 同义 BOOM 写法被采纳所需的最低频次


@dataclass(frozen=True)
class SnapResult:
    final: str
    decision: str
    detail: str


@lru_cache(maxsize=1)
def _conn() -> sqlite3.Connection | None:
    if not BOOM_INDEX_PATH.exists():
        return None
    conn = sqlite3.connect(f"file:{BOOM_INDEX_PATH}?mode=ro", uri=True)
    return conn


@lru_cache(maxsize=20000)
def _phrase_freq(term: str) -> int:
    conn = _conn()
    if conn is None:
        return 0
    row = conn.execute("SELECT freq FROM phrases WHERE phrase=?", (term,)).fetchone()
    return int(row[0]) if row else 0


@lru_cache(maxsize=20000)
def _token_freq(term: str) -> int:
    conn = _conn()
    if conn is None:
        return 0
    row = conn.execute("SELECT freq FROM tokens WHERE token=?", (term,)).fetchone()
    return int(row[0]) if row else 0


def freq(term: str) -> int:
    """BOOM 词频：单词查 tokens，多词查 phrases，取最大。"""
    term = term.strip().lower()
    if not term:
        return 0
    if " " in term:
        return max(_phrase_freq(term), _token_freq(term))
    return max(_token_freq(term), _phrase_freq(term))


def _is_common(term: str) -> bool:
    term = term.strip().lower()
    threshold = PHRASE_COMMON if " " in term else TOKEN_COMMON
    return freq(term) >= threshold


def _form_variants(term: str) -> list[str]:
    """生成「只是拼写/空格/单复数差异」的形变体候选。"""
    low = term.strip().lower()
    out: list[str] = []
    if " " in low:
        out.append(low.replace(" ", ""))     # flame thrower -> flamethrower
        out.append(low.replace(" ", "-"))    # fly by -> fly-by
    words = low.split()
    if words and words[-1].endswith("s") and len(words[-1]) > 3:
        out.append(" ".join(words[:-1] + [words[-1][:-1]]))  # 去复数
    if words and not words[-1].endswith("s"):
        out.append(" ".join(words[:-1] + [words[-1] + "s"]))  # 加复数
    # -ing 还原：flying over -> fly over
    deing = []
    changed = False
    for w in words:
        if w.endswith("ing") and len(w) > 5:
            deing.append(w[:-3])
            changed = True
        else:
            deing.append(w)
    if changed:
        out.append(" ".join(deing))
    return [v for v in out if v and v != low]


def snap_term(candidate: str, zh_token: str | None, trust: bool = False) -> SnapResult:
    """对单个英文候选做 BOOM 吸附。candidate 可为多词短语。

    trust=True 表示候选来自已策展的高优先级覆盖层（override）：只做无损的
    形变体归一（单复数/拼写/空格），不做会改词/丢词的「同义 BOOM 写法」替换，
    以免把 `Large Ice Cubes` 吞成 `Large`、`Copper Lid` 吞成 `Lid` 等。
    """
    cand = candidate.strip()
    if not cand:
        return SnapResult(cand, "empty", "")
    low = cand.lower()

    # 1) 已是 BOOM 常见写法 -> 保留
    if _is_common(low):
        return SnapResult(cand, "kept_common", f"freq={freq(low)}")

    # 2) 形变体归一（无条件，仅拼写/空格/单复数差异）
    best_form = None
    best_form_freq = 0
    for variant in _form_variants(low):
        vfreq = freq(variant)
        if vfreq > best_form_freq and fuzz.ratio(low, variant) >= FORM_SIM - 8:
            best_form, best_form_freq = variant, vfreq
    if best_form and best_form_freq >= max(VARIANT_MIN, freq(low) + 1):
        return SnapResult(
            _match_case(best_form, cand), "snapped_form",
            f"{low}->{best_form} freq={best_form_freq}",
        )

    # 3) 同义 BOOM 写法（需对齐证据 + BOOM 常见）
    # 选择标准：优先与候选词重叠多（保住信息），其次频次高，避免被泛化词吞掉。
    # 已策展覆盖层（trust）跳过本步：策展译法即期望写法，替换只会丢信息/改义。
    if zh_token and not trust:
        cand_words = set(low.split())
        base_freq = freq(low)
        best_var = None
        best_key = (-1, -1)
        for variant in align.variants_for(zh_token):
            vfreq = freq(variant)
            if vfreq < VARIANT_MIN or vfreq <= base_freq:
                continue
            overlap = len(cand_words & set(variant.split()))
            key = (overlap, vfreq)
            if key > best_key:
                best_var, best_key = variant, key
        if best_var:
            return SnapResult(
                _title(best_var), "snapped_boom_variant",
                f"{low}->{best_var} freq={best_key[1]} (aligned:{zh_token})",
            )

    # 4) 保留模型/词典输出
    return SnapResult(cand, "kept_model", f"freq={freq(low)}")


def _title(text: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in text.split())


def _match_case(variant: str, reference: str) -> str:
    """形变体沿用参考词的大小写风格（默认 Title）。"""
    return _title(variant)


if __name__ == "__main__":
    cases = [
        ("flame thrower", "喷火器"),
        ("fireworks", "喷火器"),
        ("flying over", "飞越"),
        ("take off", "起飞"),
        ("rumble", "轰鸣"),
        ("drone", "无人机"),
    ]
    for cand, zh in cases:
        r = snap_term(cand, zh)
        print(f"{cand!r:18} ({zh}) -> {r.final!r:16} [{r.decision}] {r.detail}")
