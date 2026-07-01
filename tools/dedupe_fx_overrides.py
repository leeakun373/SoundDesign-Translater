"""Keep first occurrence per raw in fx_overrides.csv (manual beats later ucs appends)."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from translator.paths import FX_OVERRIDES_PATH


def dedupe(path: Path = FX_OVERRIDES_PATH) -> int:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    removed = 0
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or ["raw", "canonical", "slot", "note"]
        for row in reader:
            raw = (row.get("raw") or "").strip()
            if not raw:
                continue
            if raw in seen:
                removed += 1
                continue
            seen.add(raw)
            rows.append(row)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return removed


if __name__ == "__main__":
    import sys
    from pathlib import Path as P
    root = P(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    n = dedupe()
