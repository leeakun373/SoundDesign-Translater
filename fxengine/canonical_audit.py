"""Read-only quality audit for the canonical token CSV."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

from fxengine.canonical_db import CANONICAL_SLOTS, DEFAULT_CANONICAL_PATH


CANONICAL_COLUMNS = (
    "raw",
    "canonical",
    "slot",
    "lang",
    "priority",
    "tags",
    "note",
)
ALLOWED_LANGS = {"zh", "en"}
TAG_RE = re.compile(r"^[a-z0-9_-]+(?:/[a-z0-9_-]+)*$")


@dataclass(frozen=True)
class CanonicalAuditIssue:
    code: str
    message: str
    row_numbers: list[int] = field(default_factory=list)
    raw: str = ""
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalAuditResult:
    path: str
    total_rows: int
    valid_rows: int
    issues: list[CanonicalAuditIssue]

    @property
    def passed(self) -> bool:
        return not self.issues

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def issue_counts(self) -> dict[str, int]:
        return dict(Counter(issue.code for issue in self.issues))

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "passed": self.passed,
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "issue_count": self.issue_count,
            "issue_counts": self.issue_counts,
            "issues": [asdict(issue) for issue in self.issues],
        }


def audit_canonical_csv(path: Path = DEFAULT_CANONICAL_PATH) -> CanonicalAuditResult:
    """Inspect CSV quality without changing the source file."""
    path = Path(path)
    if not path.is_file():
        issue = CanonicalAuditIssue(
            code="file_not_found",
            message=f"Canonical token CSV not found: {path}",
        )
        return CanonicalAuditResult(str(path), 0, 0, [issue])

    issues: list[CanonicalAuditIssue] = []
    rows: list[tuple[int, dict[str, str]]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing_columns = [column for column in CANONICAL_COLUMNS if column not in fieldnames]
        if missing_columns:
            issues.append(
                CanonicalAuditIssue(
                    code="missing_column",
                    message="Canonical CSV is missing required columns",
                    details={"columns": missing_columns},
                )
            )
        for row_number, source_row in enumerate(reader, start=2):
            row = {
                column: (source_row.get(column) or "").strip()
                for column in CANONICAL_COLUMNS
            }
            rows.append((row_number, row))
            _audit_row(row_number, row, issues)

    _audit_duplicates(rows, issues)
    issues.sort(key=lambda issue: (issue.row_numbers[:1] or [0], issue.code, issue.raw))
    problem_rows = {
        row_number for issue in issues for row_number in issue.row_numbers
    }
    return CanonicalAuditResult(
        path=str(path),
        total_rows=len(rows),
        valid_rows=max(0, len(rows) - len(problem_rows)),
        issues=issues,
    )


def _audit_row(
    row_number: int,
    row: dict[str, str],
    issues: list[CanonicalAuditIssue],
) -> None:
    raw = row["raw"]
    for column in ("raw", "canonical", "slot"):
        if not row[column]:
            issues.append(
                CanonicalAuditIssue(
                    code=f"empty_{column}",
                    message=f"{column} must not be empty",
                    row_numbers=[row_number],
                    raw=raw,
                )
            )

    priority = row["priority"]
    try:
        numeric_priority = int(priority)
    except ValueError:
        numeric_priority = None
    if numeric_priority is None or not 0 <= numeric_priority <= 100:
        issues.append(
            CanonicalAuditIssue(
                code="invalid_priority",
                message="priority must be an integer from 0 through 100",
                row_numbers=[row_number],
                raw=raw,
                details={"value": priority},
            )
        )

    if row["lang"] not in ALLOWED_LANGS:
        issues.append(
            CanonicalAuditIssue(
                code="invalid_lang",
                message="lang is outside the allowed set",
                row_numbers=[row_number],
                raw=raw,
                details={"value": row["lang"], "allowed": sorted(ALLOWED_LANGS)},
            )
        )

    if row["slot"] and row["slot"] not in CANONICAL_SLOTS:
        issues.append(
            CanonicalAuditIssue(
                code="invalid_slot",
                message="slot is outside the allowed set",
                row_numbers=[row_number],
                raw=raw,
                details={"value": row["slot"], "allowed": sorted(CANONICAL_SLOTS)},
            )
        )

    tags = row["tags"]
    if tags and not TAG_RE.fullmatch(tags):
        issues.append(
            CanonicalAuditIssue(
                code="invalid_tags",
                message="tags must be lowercase slash-separated identifiers",
                row_numbers=[row_number],
                raw=raw,
                details={"value": tags},
            )
        )


def _audit_duplicates(
    rows: list[tuple[int, dict[str, str]]],
    issues: list[CanonicalAuditIssue],
) -> None:
    exact_rows: dict[tuple[str, ...], list[int]] = defaultdict(list)
    raw_rows: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
    for row_number, row in rows:
        signature = tuple(row[column] for column in CANONICAL_COLUMNS)
        exact_rows[signature].append(row_number)
        if row["raw"]:
            raw_rows[row["raw"].casefold()].append((row_number, row))

    for signature, row_numbers in exact_rows.items():
        if len(row_numbers) > 1:
            issues.append(
                CanonicalAuditIssue(
                    code="duplicate_row",
                    message="Rows are completely identical",
                    row_numbers=row_numbers,
                    raw=signature[0],
                )
            )

    for occurrences in raw_rows.values():
        if len(occurrences) <= 1:
            continue
        row_numbers = [row_number for row_number, _row in occurrences]
        raw = occurrences[0][1]["raw"]
        issues.append(
            CanonicalAuditIssue(
                code="duplicate_raw",
                message="raw appears in multiple rows",
                row_numbers=row_numbers,
                raw=raw,
            )
        )
        canonical_values = sorted({row["canonical"] for _number, row in occurrences})
        if len(canonical_values) > 1:
            issues.append(
                CanonicalAuditIssue(
                    code="conflicting_canonical",
                    message="raw maps to multiple canonical values",
                    row_numbers=row_numbers,
                    raw=raw,
                    details={"values": canonical_values},
                )
            )
        slot_values = sorted({row["slot"] for _number, row in occurrences})
        if len(slot_values) > 1:
            issues.append(
                CanonicalAuditIssue(
                    code="conflicting_slot",
                    message="raw maps to multiple slots",
                    row_numbers=row_numbers,
                    raw=raw,
                    details={"values": slot_values},
                )
            )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=DEFAULT_CANONICAL_PATH,
        help="Canonical CSV path (defaults to fxengine/data/canonical_tokens.csv)",
    )
    args = parser.parse_args(argv)
    result = audit_canonical_csv(args.path)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
