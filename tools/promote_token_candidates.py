#!/usr/bin/env python3
"""Explicitly promote reviewed keep candidates into the canonical token table."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fxengine.canonical_audit import (  # noqa: E402
    CONFLICT_COLUMNS,
    DEFAULT_CONFLICT_PATH,
    CanonicalConflict,
)
from fxengine.canonical_db import (  # noqa: E402
    CANONICAL_COLUMNS,
    DEFAULT_CANONICAL_PATH,
    CanonicalToken,
    canonical_token_to_row,
    load_canonical_rows,
    parse_canonical_row,
)


DEFAULT_CANDIDATE_PATH = (
    ROOT / "fxengine" / "data" / "canonical_token_candidates.csv"
)


@dataclass(frozen=True)
class PromotionResult:
    candidate_count: int
    promoted_count: int
    replaced_review_count: int
    skipped_non_keep_count: int
    skipped_existing_count: int
    dry_run: bool
    conflicts: list[CanonicalConflict] = field(default_factory=list)

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    @property
    def passed(self) -> bool:
        return self.conflict_count == 0

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["conflict_count"] = self.conflict_count
        payload["passed"] = self.passed
        return payload


def promote_candidates(
    canonical_path: Path = DEFAULT_CANONICAL_PATH,
    candidate_path: Path = DEFAULT_CANDIDATE_PATH,
    conflict_path: Path = DEFAULT_CONFLICT_PATH,
    *,
    dry_run: bool = False,
) -> PromotionResult:
    canonical_path = Path(canonical_path)
    candidate_path = Path(candidate_path)
    conflict_path = Path(conflict_path)
    main_rows = load_canonical_rows(canonical_path)
    source_rows = _read_candidate_rows(candidate_path)

    conflicts: list[CanonicalConflict] = []
    parsed_candidates: list[tuple[int, CanonicalToken]] = []
    skipped_non_keep = 0
    for line_number, row in source_rows:
        try:
            candidate = parse_canonical_row(row, line_number)
        except ValueError as exc:
            conflicts.append(
                CanonicalConflict(
                    raw=(row.get("raw") or "").strip(),
                    row_numbers=[line_number],
                    canonical_values=[(row.get("canonical") or "").strip()],
                    slot_values=[(row.get("slot") or "").strip()],
                    issue_codes=["invalid_candidate"],
                    note=str(exc),
                )
            )
            continue
        if candidate.review_status != "keep":
            skipped_non_keep += 1
            continue
        parsed_candidates.append((line_number, candidate))

    duplicate_candidate_raws = _candidate_conflicts(parsed_candidates, conflicts)
    result_rows = list(main_rows)
    promoted = 0
    replaced_review = 0
    skipped_existing = 0

    for line_number, candidate in parsed_candidates:
        raw_key = candidate.raw.casefold()
        if raw_key in duplicate_candidate_raws:
            continue
        matching = [
            (index, token)
            for index, token in enumerate(result_rows)
            if token.raw.casefold() == raw_key
        ]
        runtime_matches = [
            (index, token)
            for index, token in matching
            if token.review_status == "keep"
        ]
        different_runtime = [
            token
            for _index, token in runtime_matches
            if token.canonical.casefold() != candidate.canonical.casefold()
        ]
        if different_runtime:
            values = sorted(
                {candidate.canonical, *(token.canonical for token in different_runtime)}
            )
            conflicts.append(
                CanonicalConflict(
                    raw=candidate.raw,
                    row_numbers=[line_number],
                    canonical_values=values,
                    slot_values=sorted(
                        {candidate.slot, *(token.slot for token in different_runtime)}
                    ),
                    issue_codes=["existing_keep_conflict"],
                    note="Existing keep row was not overwritten",
                )
            )
            continue
        if runtime_matches:
            skipped_existing += 1
            continue
        if len(matching) > 1:
            conflicts.append(
                CanonicalConflict(
                    raw=candidate.raw,
                    row_numbers=[line_number],
                    canonical_values=sorted(
                        {candidate.canonical, *(token.canonical for _i, token in matching)}
                    ),
                    slot_values=sorted(
                        {candidate.slot, *(token.slot for _i, token in matching)}
                    ),
                    issue_codes=["multiple_non_runtime_rows"],
                    note="Resolve duplicate review/reject rows before promotion",
                )
            )
            continue
        if matching:
            result_rows[matching[0][0]] = candidate
            replaced_review += 1
        else:
            result_rows.append(candidate)
        promoted += 1

    result = PromotionResult(
        candidate_count=len(source_rows),
        promoted_count=promoted,
        replaced_review_count=replaced_review,
        skipped_non_keep_count=skipped_non_keep,
        skipped_existing_count=skipped_existing,
        dry_run=dry_run,
        conflicts=conflicts,
    )
    _write_conflicts(conflict_path, conflicts)
    if promoted and not dry_run:
        _write_canonical_rows(canonical_path, result_rows)
    return result


def _read_candidate_rows(path: Path) -> list[tuple[int, dict[str, str]]]:
    if not path.is_file():
        raise FileNotFoundError(f"Candidate CSV not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CANONICAL_COLUMNS:
            raise ValueError(
                "Candidate CSV fields must exactly match canonical schema: "
                + ",".join(CANONICAL_COLUMNS)
            )
        return [
            (line_number, {key: value or "" for key, value in row.items()})
            for line_number, row in enumerate(reader, start=2)
        ]


def _candidate_conflicts(
    candidates: list[tuple[int, CanonicalToken]],
    conflicts: list[CanonicalConflict],
) -> set[str]:
    grouped: dict[str, list[tuple[int, CanonicalToken]]] = {}
    for item in candidates:
        grouped.setdefault(item[1].raw.casefold(), []).append(item)
    blocked: set[str] = set()
    for raw_key, occurrences in grouped.items():
        if len(occurrences) <= 1:
            continue
        values = {token.canonical.casefold() for _line, token in occurrences}
        if len(values) == 1:
            # Duplicate candidate input is still unsafe to apply implicitly.
            issue_code = "duplicate_candidate_raw"
        else:
            issue_code = "candidate_canonical_conflict"
        blocked.add(raw_key)
        conflicts.append(
            CanonicalConflict(
                raw=occurrences[0][1].raw,
                row_numbers=[line for line, _token in occurrences],
                canonical_values=sorted(
                    {token.canonical for _line, token in occurrences}
                ),
                slot_values=sorted({token.slot for _line, token in occurrences}),
                issue_codes=[issue_code],
                note="No candidate with this raw was promoted",
            )
        )
    return blocked


def _write_canonical_rows(path: Path, rows: list[CanonicalToken]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CANONICAL_COLUMNS)
            writer.writeheader()
            writer.writerows(canonical_token_to_row(token) for token in rows)
        Path(temp_name).replace(path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


def _write_conflicts(path: Path, conflicts: list[CanonicalConflict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CONFLICT_COLUMNS)
        writer.writeheader()
        writer.writerows(conflict.to_csv_row() for conflict in conflicts)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL_PATH)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATE_PATH)
    parser.add_argument("--conflicts", type=Path, default=DEFAULT_CONFLICT_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = promote_candidates(
            canonical_path=args.canonical,
            candidate_path=args.candidates,
            conflict_path=args.conflicts,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
