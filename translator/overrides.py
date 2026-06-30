"""Canonical 覆盖层：从 fxengine/data/canonical_tokens.csv 读取受治理的 zh->en 映射。

本引擎只读该表（不修改），作为最高优先级覆盖（FX 策展译法）与禁词来源。
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

CANONICAL_PATH = (
    Path(__file__).resolve().parent.parent
    / "fxengine"
    / "data"
    / "canonical_tokens.csv"
)
# translator 自有的小型「手工」策展层（最高优先级；修正 cedict 误义/自动误判）。
FX_OVERRIDES_PATH = Path(__file__).resolve().parent / "data" / "fx_overrides.csv"
# 数据驱动「自动」策展层（由 tools/mine_overrides.py 从 BOOM 词频生成；低维护）。
FX_OVERRIDES_AUTO_PATH = Path(__file__).resolve().parent / "data" / "fx_overrides_auto.csv"
# 双语挖掘层（由 tools/mine_overrides_bilingual.py 从精翻对照学到；观测真值，高可信）。
FX_OVERRIDES_BILINGUAL_PATH = Path(__file__).resolve().parent / "data" / "fx_overrides_bilingual.csv"
# 短语(2-gram)覆盖层：解决多义词上下文（开关 关闭->Switch Off）。
FX_OVERRIDES_PHRASE_PATH = Path(__file__).resolve().parent / "data" / "fx_overrides_phrase.csv"


def _read_override_csv(path: Path) -> dict[str, dict[str, str]]:
    table: dict[str, dict[str, str]] = {}
    if not path.exists():
        return table
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            raw = (row.get("raw") or "").strip()
            canonical = (row.get("canonical") or "").strip()
            if not raw or not canonical:
                continue
            table[raw] = {
                "canonical": canonical,
                "slot": (row.get("slot") or "").strip(),
                "priority": "999",
            }
    return table


@lru_cache(maxsize=1)
def _load() -> dict[str, dict[str, str]]:
    """raw(zh) -> {canonical, slot}。优先级：手工 > 双语挖掘 > canonical(keep) > cedict自动。"""
    table = _read_override_csv(FX_OVERRIDES_AUTO_PATH)       # 最低：cedict×词频（弱）
    table.update(_load_canonical())                          # canonical(keep) 覆盖自动
    table.update(_read_override_csv(FX_OVERRIDES_BILINGUAL_PATH))  # 双语观测真值覆盖 canonical
    table.update(_read_override_csv(FX_OVERRIDES_PATH))       # 手工最高
    return table


@lru_cache(maxsize=1)
def manual_keys() -> frozenset[str]:
    """手工策展层覆盖的中文 token（供自动挖掘排除）。"""
    return frozenset(_read_override_csv(FX_OVERRIDES_PATH))


def _load_canonical() -> dict[str, dict[str, str]]:
    """raw(zh) -> {canonical, slot}，仅取 lang=zh 且 review_status=keep 且 canonical 非空。"""
    table: dict[str, dict[str, str]] = {}
    if not CANONICAL_PATH.exists():
        return table
    with CANONICAL_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("lang") != "zh":
                continue
            if row.get("review_status") != "keep":
                continue
            raw = (row.get("raw") or "").strip()
            canonical = (row.get("canonical") or "").strip()
            if not raw or not canonical:
                continue
            # 同一 raw 取优先级更高者
            existing = table.get(raw)
            if existing is not None:
                try:
                    if int(row.get("priority") or 0) <= int(existing.get("priority") or 0):
                        continue
                except ValueError:
                    continue
            table[raw] = {
                "canonical": canonical,
                "slot": (row.get("slot") or "").strip(),
                "priority": row.get("priority") or "0",
            }
    return table


@lru_cache(maxsize=1)
def _load_phrases() -> dict[str, str]:
    """中文相邻2词("a b") -> 英文短语。空表也合法。"""
    table: dict[str, str] = {}
    if not FX_OVERRIDES_PHRASE_PATH.exists():
        return table
    with FX_OVERRIDES_PHRASE_PATH.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            raw = (row.get("raw") or "").strip()
            canonical = (row.get("canonical") or "").strip()
            if raw and canonical:
                table[raw] = canonical
    return table


def phrase_lookup(first: str, second: str) -> str | None:
    return _load_phrases().get(f"{first} {second}")


def lookup(word: str) -> dict[str, str] | None:
    return _load().get(word)


def keys() -> list[str]:
    return list(_load())


def is_loaded() -> bool:
    return bool(_load())


if __name__ == "__main__":
    table = _load()
    print(f"canonical zh keep mappings: {len(table)}")
    for word in ["金属", "门", "雷", "涡轮", "飞走", "喷火器"]:
        print(f"{word} -> {lookup(word)}")
