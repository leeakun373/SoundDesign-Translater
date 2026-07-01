"""Conservatively merge UCS Synonyms_zh into fx_overrides.csv."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
_ASCII_RE = re.compile(r"^[A-Za-z0-9+\-]+$")


def _split_zh_list(value: str) -> list[str]:
    if not value or not value.strip():
        return []
    parts: list[str] = []
    for chunk in value.replace("、", ",").split(","):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts


def _title(word: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in word.split())


def ingest(ucs_path: Path, overrides_path: Path, *, apply: bool) -> dict:
    from translator import overrides

    rows_ucs = list(csv.DictReader(ucs_path.open(encoding="utf-8-sig")))
    existing = {}
    if overrides_path.is_file():
        with overrides_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                raw = (row.get("raw") or "").strip()
                if raw:
                    existing[raw] = row
    proposed: dict[str, dict[str, str]] = {}
    conflicts: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    for row in rows_ucs:
        sub_en = _title((row.get("SubCategory") or "").strip())
        if not sub_en:
            continue
        for zh_syn in _split_zh_list(row.get("Synonyms_zh") or ""):
            if len(zh_syn) < 2:
                skipped.append({"zh": zh_syn, "reason": "single_char"})
                continue
            if _ASCII_RE.fullmatch(zh_syn):
                skipped.append({"zh": zh_syn, "reason": "ascii"})
                continue
            if not _CJK_RE.search(zh_syn):
                skipped.append({"zh": zh_syn, "reason": "no_cjk"})
                continue
            if zh_syn in existing or zh_syn in proposed:
                old = existing.get(zh_syn, {}).get("canonical") or proposed.get(zh_syn, {}).get("canonical")
                if old and old != sub_en:
                    conflicts.append({"zh": zh_syn, "existing": old, "proposed": sub_en})
                continue
            proposed[zh_syn] = {
                "raw": zh_syn,
                "canonical": sub_en,
                "slot": "detail",
                "note": "ucs_synonym_zh",
            }

    REPORTS.mkdir(parents=True, exist_ok=True)
    conflicts_path = REPORTS / "ucs_zh_synonym_conflicts.csv"
    with conflicts_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["zh", "existing", "proposed"])
        writer.writeheader()
        writer.writerows(conflicts)

    if apply and proposed:
        fieldnames = ["raw", "canonical", "slot", "note"]
        with overrides_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            for item in sorted(proposed.values(), key=lambda x: x["raw"]):
                writer.writerow(item)
        overrides._load.cache_clear()
        overrides.manual_keys.cache_clear()

    return {
        "proposed": len(proposed),
        "conflicts": len(conflicts),
        "skipped": len(skipped),
        "applied": apply,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest UCS zh synonyms into fx_overrides.")
    parser.add_argument("--ucs", type=Path, default=None)
    parser.add_argument("--overrides", type=Path, default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    from translator.paths import FX_OVERRIDES_PATH, UCS_CATID_CSV
    stats = ingest(
        args.ucs or UCS_CATID_CSV,
        args.overrides or FX_OVERRIDES_PATH,
        apply=bool(args.apply),
    )
    print(stats)
    if args.apply:
        from translator import align
        align.build()
        print("Rebuilt zh_en_alignment.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
