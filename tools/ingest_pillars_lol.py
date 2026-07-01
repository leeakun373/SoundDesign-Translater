"""Ingest League of Legends pillars skin lines into fx_overrides."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _split_keywords(value: str) -> list[str]:
    if not value or not value.strip():
        return []
    return [part.strip().lower() for part in value.split(",") if part.strip()]


def _load_skinlines(path: Path) -> dict[str, dict[str, str]]:
    table: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            en = (row.get("concept_en") or "").strip()
            if en:
                table[en] = row
    return table


def ingest(
    pillars_path: Path,
    skinlines_path: Path,
    overrides_path: Path,
    *,
    apply: bool,
) -> dict:
    from translator import boom_snap, overrides

    pillars = list(csv.DictReader(pillars_path.open(encoding="utf-8")))
    skinlines = _load_skinlines(skinlines_path)
    existing = set(overrides.manual_keys())

    missing_zh: list[str] = []
    proposed: list[dict[str, str]] = []
    keyword_gaps: list[dict[str, str]] = []
    known_en = {k.lower() for k in overrides.keys()}

    for row in pillars:
        concept = (row.get("Concept") or "").strip()
        if not concept:
            continue
        mapping = skinlines.get(concept)
        if not mapping or (mapping.get("verified") or "").lower() != "true":
            missing_zh.append(concept)
            continue
        zh = (mapping.get("concept_zh") or "").strip()
        en = concept
        if zh and zh not in existing:
            proposed.append({
                "raw": zh,
                "canonical": en,
                "slot": "modifier",
                "note": "lol_pillar",
            })
        for kw in _split_keywords(row.get("Keywords") or ""):
            if kw in known_en:
                continue
            freq = boom_snap.freq(kw)
            keyword_gaps.append({
                "keyword": kw,
                "concept": concept,
                "boom_freq": str(freq),
            })

    REPORTS.mkdir(parents=True, exist_ok=True)
    gaps_path = REPORTS / "pillars_keywords_gap.csv"
    with gaps_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["keyword", "concept", "boom_freq"])
        writer.writeheader()
        writer.writerows(keyword_gaps)

    missing_path = REPORTS / "pillars_missing_zh.md"
    if missing_zh:
        missing_path.write_text(
            "# Pillars concepts missing verified Chinese mapping\n\n"
            + "\n".join(f"- {item}" for item in missing_zh)
            + "\n",
            encoding="utf-8",
        )

    if apply and proposed:
        fieldnames = ["raw", "canonical", "slot", "note"]
        with overrides_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            for item in proposed:
                writer.writerow(item)
        overrides._load.cache_clear()
        overrides.manual_keys.cache_clear()

    return {
        "pillars": len(pillars),
        "proposed": len(proposed),
        "missing_zh": len(missing_zh),
        "keyword_gaps": len(keyword_gaps),
        "applied": apply,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest LoL pillars into fx_overrides.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    from translator.paths import FX_OVERRIDES_PATH, LOL_SKINLINES_ZH_CSV, PILLARS_DATA_CSV
    stats = ingest(PILLARS_DATA_CSV, LOL_SKINLINES_ZH_CSV, FX_OVERRIDES_PATH, apply=bool(args.apply))
    print(stats)
    if args.apply:
        from translator import align
        align.build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
