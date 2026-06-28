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
# translator 自有的小型策展覆盖层（优先级高于 canonical；修正 cedict 误义、统一 BOOM 写法）。
FX_OVERRIDES_PATH = Path(__file__).resolve().parent / "data" / "fx_overrides.csv"


@lru_cache(maxsize=1)
def _load() -> dict[str, dict[str, str]]:
    """raw(zh) -> {canonical, slot}。fx_overrides 优先，其次 canonical keep。"""
    table = _load_canonical()
    # fx_overrides 覆盖（最高优先级）
    if FX_OVERRIDES_PATH.exists():
        with FX_OVERRIDES_PATH.open(encoding="utf-8", newline="") as handle:
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
