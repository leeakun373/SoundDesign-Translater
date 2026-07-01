"""CC-CEDICT 清洗与查询。

CC-CEDICT 在本引擎里只承担：
1. 分词词典种子（jieba userdict）——保证「喷火器」「遥控无人机」整词不被拆。
2. 术语兜底/候选——当 canonical 无覆盖时，给出比 NLLB 更可靠的孤立词译法
   （例如「喷火器」NLLB 误译 Fireworks，CC-CEDICT 给 flamethrower）。

它不负责 FXName 最终风格（风格交给 BOOM 吸附层）。
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from translator.paths import CEDICT_PATH

_LINE_RE = re.compile(r"^(\S+)\s+(\S+)\s+\[[^\]]*\]\s+/(.+)/\s*$")
_PAREN_RE = re.compile(r"\([^)]*\)")
_SKIP_PREFIXES = (
    "CL:",
    "variant of",
    "old variant of",
    "see ",
    "see also",
    "erhua variant",
    "abbr. for",
    "abbr ",
)


def _clean_gloss(gloss: str) -> str:
    """把一个释义子句压成 FXName 友好的短关键词。"""
    text = gloss.strip()
    # 去掉括注，如 boom (sound of explosion) -> boom
    text = _PAREN_RE.sub("", text).strip()
    # 去掉冠词 / 不定式前缀，使其更像命名关键词
    for prefix in ("to ", "a ", "an ", "the "):
        if text.lower().startswith(prefix):
            text = text[len(prefix):].strip()
            break
    text = re.sub(r"\s+", " ", text).strip(" .,")
    return text


def _expand_senses(raw_gloss: str) -> list[str]:
    """一条释义可能含多个 ';' 子义，逐个展开成候选关键词。"""
    out: list[str] = []
    for sub in raw_gloss.split(";"):
        cleaned = _clean_gloss(sub)
        if cleaned:
            out.append(cleaned)
    return out


def _is_useful(raw_gloss: str) -> bool:
    low = raw_gloss.strip().lower()
    if not low:
        return False
    for prefix in _SKIP_PREFIXES:
        if low.startswith(prefix.lower()):
            return False
    return True


def _score_gloss(gloss: str) -> tuple[int, int, int]:
    """越小越优先：非姓氏 > 词数少 > 长度短。"""
    low = gloss.lower()
    is_surname = 1 if low.startswith("surname ") else 0
    word_count = len(gloss.split())
    return (is_surname, word_count, len(gloss))


@lru_cache(maxsize=1)
def _load() -> dict[str, list[str]]:
    """simp -> 按优先级排序的清洗后释义列表。"""
    table: dict[str, list[str]] = {}
    if not CEDICT_PATH.exists():
        return table
    with CEDICT_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            match = _LINE_RE.match(line)
            if not match:
                continue
            simp = match.group(2)
            raw_defs = match.group(3).split("/")
            for raw in raw_defs:
                if not _is_useful(raw):
                    continue
                for cleaned in _expand_senses(raw):
                    table.setdefault(simp, []).append(cleaned)
    # 去重 + 按 FXName 友好度排序
    for simp, glosses in table.items():
        seen: set[str] = set()
        unique: list[str] = []
        for gloss in glosses:
            key = gloss.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(gloss)
        unique.sort(key=_score_gloss)
        table[simp] = unique
    return table


def lookup_all(word: str) -> list[str]:
    """返回某中文词的全部清洗后英文候选（已按优先级排序）。"""
    return list(_load().get(word, ()))


def lookup(word: str) -> str | None:
    """返回最适合做命名关键词的单个英文释义；无则 None。"""
    glosses = _load().get(word)
    if not glosses:
        return None
    return glosses[0]


def headwords(min_len: int = 2) -> list[str]:
    """返回长度 >= min_len 的简体词头，用于构建 jieba 词典。"""
    return [w for w in _load() if len(w) >= min_len]


def is_loaded() -> bool:
    return bool(_load())


if __name__ == "__main__":
    samples = ["喷火器", "遥控", "无人机", "金属", "门", "雷", "轰鸣", "直升机"]
    table = _load()
    print(f"CC-CEDICT entries (simplified headwords): {len(table)}")
    for word in samples:
        print(f"{word} -> {lookup(word)!r}  (all: {lookup_all(word)[:4]})")
