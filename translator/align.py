"""中英对齐表：zh_token -> {en_variant: support}。

用途：BOOM 吸附层做「同义替换」时的「符合中文输入」证据闸门——
只有当某个 BOOM 候选写法 Q 确实是输入里某个中文 token 的合法译法时，才允许替换。

三源合并（support 权重）：
- canonical_tokens.csv keep        : 3（FX 策展，最可信）
- boom_one mining candidates       : 2（双语对齐挖掘，promote_ready 优先）
- CC-CEDICT                        : 1（通用词典兜底）
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from translator import cedict, overrides

ALIGN_PATH = Path(__file__).resolve().parent / "data" / "zh_en_alignment.csv"
CANDIDATES_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "boom_mining"
    / "boom_one_mining_v0_1_b001_candidates.csv"
)


def _add(table: dict[str, dict[str, int]], zh: str, en: str, support: int) -> None:
    zh = (zh or "").strip()
    en = (en or "").strip()
    if not zh or not en:
        return
    bucket = table.setdefault(zh, {})
    bucket[en] = max(bucket.get(en, 0), support)


def build(path: Path = ALIGN_PATH) -> int:
    """构建对齐 CSV，返回 (zh,en) 行数。"""
    table: dict[str, dict[str, int]] = {}

    # 1) canonical keep
    for zh in overrides.keys():
        entry = overrides.lookup(zh)
        if entry:
            _add(table, zh, entry["canonical"], 3)

    # 2) boom_one mining candidates（跳过不安全/冲突/单字）
    if CANDIDATES_PATH.exists():
        with CANDIDATES_PATH.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if row.get("lang") != "zh":
                    continue
                status = (row.get("candidate_status") or "").strip()
                if status in {"unsafe", "conflict"}:
                    continue
                zh = row.get("suggested_raw") or ""
                en = row.get("suggested_canonical") or ""
                if len(zh.strip()) < 2:  # 单字证据太弱，跳过
                    continue
                _add(table, zh, en, 2)

    # 3) CC-CEDICT 全量词头（兜底）
    for zh in cedict.headwords(min_len=2):
        for gloss in cedict.lookup_all(zh)[:3]:
            _add(table, zh, gloss, 1)

    rows = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["zh", "en", "support"])
        for zh in sorted(table):
            for en, support in sorted(table[zh].items(), key=lambda kv: -kv[1]):
                writer.writerow([zh, en, support])
                rows += 1
    return rows


@lru_cache(maxsize=1)
def _load() -> dict[str, set[str]]:
    """zh -> 合法英文译法集合（全部小写，含整短语与单词）。"""
    table: dict[str, set[str]] = {}
    if not ALIGN_PATH.exists():
        build()
    with ALIGN_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            zh = (row.get("zh") or "").strip()
            en = (row.get("en") or "").strip().lower()
            if not zh or not en:
                continue
            bucket = table.setdefault(zh, set())
            bucket.add(en)
            for word in en.split():
                bucket.add(word)
    return table


def variants_for(zh: str) -> set[str]:
    """某中文 token 的全部合法英文（小写，含单词级）。"""
    return _load().get(zh, set())


def supports(zh_tokens: list[str], candidate_en: str) -> bool:
    """candidate_en 是否为输入中任一中文 token 的合法译法。"""
    cand = candidate_en.strip().lower()
    if not cand:
        return False
    for zh in zh_tokens:
        bucket = _load().get(zh)
        if not bucket:
            continue
        if cand in bucket:
            return True
        # 整短语候选：要求其每个词都被该 token 支持
        words = cand.split()
        if len(words) > 1 and all(w in bucket for w in words):
            return True
    return False


if __name__ == "__main__":
    count = build()
    print(f"alignment rows: {count} -> {ALIGN_PATH}")
    for zh in ["奥古斯塔", "飞走", "稳定", "序列", "喷火器", "无人机"]:
        print(f"{zh} -> {sorted(variants_for(zh))[:6]}")
