#!/usr/bin/env python3
"""zh_compose 单元自测。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from glossary.matcher import GlossaryMatcher
from glossary.zh_compose import compose_zh_to_en


def main() -> None:
    m = GlossaryMatcher()
    cases = [
        ("拧螺丝，咔哒几声，然后关上", ["Screw", "Clicks", "Shut"]),
        ("外面汽车开过去呼呼的，带混响", ["Exterior", "Car", "Driveby", "Whoosh", "Reverberant"]),
        ("弓搭箭，皮托，拉弦", ["Bow", "Nocked", "Leatherrest", "Drawing"]),
        ("冰斧刮擦冰砖的摩擦声", ["Ice Axe", "Scratch", "Ice Brick", "Friction"]),
        ("空办公室里的房间底噪，有一点混响", ["Empty", "Office", "Room Tone", "Reverberant"]),
        ("落叶林清晨鸟叫，偶尔有蛙鸣", ["decid", "Early Morning", "Birds", "Occasional", "croak"]),
    ]
    for text, expect in cases:
        out, hits = compose_zh_to_en(text, m)
        missing = [w for w in expect if w.lower() not in out.lower()]
        status = "OK" if not missing else f"MISS {missing}"
        print(f"[{status}] {text}")
        print(f"  -> {out} (hits={hits})")


if __name__ == "__main__":
    main()
