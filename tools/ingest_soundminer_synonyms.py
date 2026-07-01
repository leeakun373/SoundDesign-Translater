"""Parse soundminer.tth into en_synonym_groups.csv."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_tth(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    canonical = ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(":"):
            canonical = line[1:].strip().lower()
            continue
        if not canonical:
            continue
        for part in line.split(","):
            variant = part.strip().lower()
            if variant and variant != canonical:
                rows.append((canonical, variant))
    return rows


def ingest(source: Path, out: Path) -> int:
    text = source.read_text(encoding="utf-8", errors="replace")
    rows = parse_tth(text)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["canonical", "variant", "source"])
        writer.writeheader()
        for canonical, variant in rows:
            writer.writerow({"canonical": canonical, "variant": variant, "source": "soundminer"})
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest soundminer.tth synonym groups.")
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    from translator.paths import EN_SYNONYM_GROUPS_CSV, SOUNDMINER_TTH
    source = args.source or SOUNDMINER_TTH
    out = args.out or EN_SYNONYM_GROUPS_CSV
    count = ingest(source, out)
    print(f"Wrote {count} synonym pairs -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
