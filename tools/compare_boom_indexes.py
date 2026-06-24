#!/usr/bin/env python3
"""Compare baseline / filename-only / cleaned Boom style indexes (temporary)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import NllbTranslator
from glossary.boom_style import BoomStyleIndex

GLOSSARY = ROOT / "glossary"
INDEXES = {
    "baseline": GLOSSARY / "boom_style_index_baseline.sqlite",
    "filename_only": GLOSSARY / "boom_style_index_filename_only.sqlite",
    "cleaned": GLOSSARY / "boom_style_index_cleaned.sqlite",
}
SMOKE_CASES = [
    "木门滑开",
    "金属撞击",
    "塑料盒掉落",
    "水流过石头",
    "火箭狼嚎飞过",
    "玻璃杯子掉落破碎",
    "布椅子拖动摩擦",
    "纸张撕裂",
    "皮革摩擦",
    "石头滚动",
]
FOCUS = {"塑料盒掉落", "水流过石头"}


def index_stats(path: Path) -> dict:
    with sqlite3.connect(path) as conn:
        stats = dict(conn.execute("SELECT key, value FROM stats").fetchall())
        top_tokens = conn.execute(
            "SELECT token, freq, filename_freq FROM tokens ORDER BY freq DESC LIMIT 50"
        ).fetchall()
        top_phrases = conn.execute(
            "SELECT phrase, n, freq, filename_freq FROM phrases ORDER BY freq DESC LIMIT 50"
        ).fetchall()
        top_fn = conn.execute(
            "SELECT phrase, n, freq, filename_freq FROM phrases ORDER BY filename_freq DESC LIMIT 50"
        ).fetchall()
    return {
        "files_read": int(stats.get("files_read", 0)),
        "english_lines": int(stats.get("english_lines", 0)),
        "top_50_tokens": [
            {"token": t, "freq": f, "filename_freq": ff} for t, f, ff in top_tokens
        ],
        "top_50_phrases_by_freq": [
            {"phrase": p, "n": n, "freq": f, "filename_freq": ff}
            for p, n, f, ff in top_phrases
        ],
        "top_50_phrases_by_filename_freq": [
            {"phrase": p, "n": n, "freq": f, "filename_freq": ff}
            for p, n, f, ff in top_fn
        ],
    }


def run_smoke(translator: NllbTranslator, index_path: Path) -> list[dict]:
    translator._boom_style = BoomStyleIndex(index_path)
    out: list[dict] = []
    for text in SMOKE_CASES:
        r = translator.translate(text, mode="sentence", pro_mode=True)
        out.append(
            {
                "input": text,
                "translation": r.text,
                "debug": r.debug,
            }
        )
    return out


def odd_order(translation: str) -> list[str]:
    flags: list[str] = []
    lower = translation.lower()
    pairs = [
        ("drop box", "Box 在 Drop 前（常见应为 Box Drop）"),
        ("plastic drop box", "塑料盒：Drop 在 Box 前"),
        ("flow stone", "水流过石头：缺少 water/flow over 语义"),
    ]
    for needle, msg in pairs:
        if needle in lower:
            flags.append(msg)
    return flags


def main() -> int:
    print("Loading translator once for smoke cases...")
    translator = NllbTranslator()
    translator.load()

    report: dict = {"indexes": {}, "smoke": {}}
    for name, path in INDEXES.items():
        if not path.is_file():
            print(f"MISSING: {path}")
            return 1
        report["indexes"][name] = index_stats(path)
        report["smoke"][name] = run_smoke(translator, path)

    out_path = ROOT / "tests" / "results" / "_index_compare_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {out_path}")
    for name in INDEXES:
        s = report["indexes"][name]
        print(f"\n=== {name} ===")
        print(f"files_read={s['files_read']} english_lines={s['english_lines']}")
        print("top5 tokens:", s["top_50_tokens"][:5])
        print("top5 phrases:", s["top_50_phrases_by_freq"][:5])

    print("\n=== SMOKE FOCUS ===")
    for case in SMOKE_CASES:
        row = {k: report["smoke"][k] for k in INDEXES}
        vals = {k: next(x for x in row[k] if x["input"] == case)["translation"] for k in INDEXES}
        print(f"{case}: baseline={vals['baseline']!r} | fn_only={vals['filename_only']!r} | cleaned={vals['cleaned']!r}")
        if case in FOCUS:
            for k, v in vals.items():
                flags = odd_order(v)
                if flags:
                    print(f"  [{k}] flags: {flags}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
