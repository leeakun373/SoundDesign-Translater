"""UCS CatID coverage audit and gap reports."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _split_csv_list(value: str) -> list[str]:
    if not value or not value.strip():
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _split_zh_list(value: str) -> list[str]:
    if not value or not value.strip():
        return []
    parts: list[str] = []
    for chunk in value.replace("、", ",").split(","):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts


def audit(ucs_path: Path, report_dir: Path) -> dict:
    from translator import overrides

    rows = list(csv.DictReader(ucs_path.open(encoding="utf-8-sig")))
    categories = {r["Category"].strip() for r in rows if r.get("Category")}
    subcats = {(r["Category"].strip(), r["SubCategory"].strip()) for r in rows if r.get("SubCategory")}

    missing_cat_zh = [r for r in rows if not (r.get("Category_zh") or "").strip()]
    missing_sub_zh = [r for r in rows if not (r.get("SubCategory_zh") or "").strip()]

    override_keys = set(overrides.keys())
    zh_gaps: list[dict[str, str]] = []
    en_syns: set[str] = set()
    zh_syns_all: set[str] = set()

    for row in rows:
        sub_en = (row.get("SubCategory") or "").strip()
        for syn in _split_csv_list(row.get("Synonyms - Comma Separated") or ""):
            if syn:
                en_syns.add(syn.lower())
        for zh_syn in _split_zh_list(row.get("Synonyms_zh") or ""):
            if not zh_syn:
                continue
            zh_syns_all.add(zh_syn)
            if zh_syn not in override_keys:
                zh_gaps.append({
                    "zh_synonym": zh_syn,
                    "subcategory_en": sub_en,
                    "category": (row.get("Category") or "").strip(),
                    "catid": (row.get("CatID") or "").strip(),
                })

    report_dir.mkdir(parents=True, exist_ok=True)
    gaps_path = report_dir / "ucs_zh_synonym_gaps.csv"
    with gaps_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["zh_synonym", "subcategory_en", "category", "catid"])
        writer.writeheader()
        writer.writerows(zh_gaps)

    summary_path = report_dir / "ucs_coverage_audit.md"
    lines = [
        "# UCS CatID Coverage Audit",
        "",
        f"- UCS rows: {len(rows)}",
        f"- Categories: {len(categories)} (expected 82)",
        f"- Subcategories: {len(subcats)} (expected 753)",
        f"- Missing Category_zh: {len(missing_cat_zh)}",
        f"- Missing SubCategory_zh: {len(missing_sub_zh)}",
        f"- Unique EN synonyms: {len(en_syns)}",
        f"- Unique Synonyms_zh: {len(zh_syns_all)}",
        f"- Synonyms_zh not in fx_overrides keys: {len(zh_gaps)}",
        f"- Gap CSV: `{gaps_path.relative_to(ROOT).as_posix()}`",
        "",
    ]
    if len(categories) != 82 or len(subcats) != 753:
        lines.append("**WARNING**: category/subcategory counts differ from expected 82/753.")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "rows": len(rows),
        "categories": len(categories),
        "subcats": len(subcats),
        "zh_gaps": len(zh_gaps),
        "summary": str(summary_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit UCS CatID coverage and zh synonym gaps.")
    parser.add_argument(
        "--ucs",
        type=Path,
        default=None,
        help="ucs_catid_list.csv (default: translator_assets glossary source)",
    )
    parser.add_argument("--report-dir", type=Path, default=REPORTS)
    args = parser.parse_args(argv)
    if args.ucs is None:
        from translator.paths import UCS_CATID_CSV
        ucs_path = UCS_CATID_CSV
    else:
        ucs_path = args.ucs
    stats = audit(ucs_path, args.report_dir)
    print(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
