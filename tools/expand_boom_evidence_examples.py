#!/usr/bin/env python3
"""Expand BOOM candidate evidence examples from SQLite before AI prompt packing."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fxengine.canonical_db import DEFAULT_CANONICAL_PATH  # noqa: E402
from tools.build_boom_candidate_evidence import (  # noqa: E402,F401
    EVIDENCE_COLUMNS,
    EXPANDED_EXAMPLE_COLUMNS,
    expand_examples_for_candidate,
    rescore_candidate_with_expanded_examples,
    score_example_quality,
    select_best_examples,
)

DEFAULT_DB = ROOT / "data" / "boomone" / "boomone_records.sqlite"
DEFAULT_CANDIDATE_EVIDENCE = (
    ROOT / "exports" / "boomone_candidates" / "candidate_evidence.csv"
)
DEFAULT_OUTPUT_DIR = ROOT / "exports" / "boomone_candidates"
DEFAULT_REPORT = ROOT / "reports" / "boom_evidence_expansion_report.md"
DEFAULT_CANONICAL = DEFAULT_CANONICAL_PATH


@dataclass(frozen=True)
class ExpansionSummary:
    total_candidate_rows: int
    expanded_evidence_rows: int
    average_examples_per_candidate: float
    before_approved_for_ai_count: int
    after_approved_for_ai_count: int
    expanded_examples_path: str
    expanded_candidate_evidence_path: str
    report_path: str
    canonical_tokens_sha256_before: str
    canonical_tokens_sha256_after: str
    canonical_tokens_changed: bool


def expand_candidate_evidence(
    candidate_evidence_path: Path = DEFAULT_CANDIDATE_EVIDENCE,
    db_path: Path = DEFAULT_DB,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    report_path: Path = DEFAULT_REPORT,
    canonical_path: Path = DEFAULT_CANONICAL,
    *,
    max_examples_per_candidate: int = 20,
) -> ExpansionSummary:
    candidate_evidence_path = Path(candidate_evidence_path)
    db_path = Path(db_path)
    output_dir = Path(output_dir)
    report_path = Path(report_path)
    canonical_path = Path(canonical_path)
    for path in (candidate_evidence_path, db_path, canonical_path):
        if not path.is_file():
            raise FileNotFoundError(f"Required input not found: {path}")
    if max_examples_per_candidate < 1:
        raise ValueError("max_examples_per_candidate must be positive")

    canonical_before = _sha256(canonical_path)
    candidates = _read_candidate_rows(candidate_evidence_path)
    before_approved = sum(
        row.get("approved_for_ai") == "yes" for row in candidates
    )
    expanded_rows: list[dict[str, str]] = []
    rescored_rows: list[dict[str, object]] = []

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        _assert_table(connection)
        for row in candidates:
            examples = expand_examples_for_candidate(
                connection,
                row["raw"],
                row.get("canonical_guess", ""),
                max_examples=max_examples_per_candidate,
            )
            expanded_rows.extend(examples)
            rescored_rows.append(
                rescore_candidate_with_expanded_examples(row, examples)
            )
    finally:
        connection.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    expanded_examples_path = output_dir / "expanded_examples.csv"
    expanded_candidate_path = output_dir / "candidate_evidence_expanded.csv"
    _write_csv(expanded_examples_path, EXPANDED_EXAMPLE_COLUMNS, expanded_rows)
    _write_csv(expanded_candidate_path, EVIDENCE_COLUMNS, rescored_rows)

    canonical_after = _sha256(canonical_path)
    if canonical_after != canonical_before:
        raise RuntimeError("canonical_tokens.csv changed while expanding evidence")
    summary = ExpansionSummary(
        total_candidate_rows=len(candidates),
        expanded_evidence_rows=len(expanded_rows),
        average_examples_per_candidate=(
            len(expanded_rows) / len(candidates) if candidates else 0.0
        ),
        before_approved_for_ai_count=before_approved,
        after_approved_for_ai_count=sum(
            row.get("approved_for_ai") == "yes" for row in rescored_rows
        ),
        expanded_examples_path=str(expanded_examples_path),
        expanded_candidate_evidence_path=str(expanded_candidate_path),
        report_path=str(report_path),
        canonical_tokens_sha256_before=canonical_before,
        canonical_tokens_sha256_after=canonical_after,
        canonical_tokens_changed=False,
    )
    _write_report(report_path, summary, rescored_rows, expanded_rows)
    return summary


def _read_candidate_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not set(EVIDENCE_COLUMNS) <= set(reader.fieldnames):
            raise ValueError(f"{path} is missing candidate evidence columns")
        return [{key: value or "" for key, value in row.items()} for row in reader]


def _assert_table(connection: sqlite3.Connection) -> None:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='boomone_records'"
    ).fetchone()
    if exists is None:
        raise ValueError("boomone_records table is missing")


def _write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[dict[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_report(
    path: Path,
    summary: ExpansionSummary,
    rows: list[dict[str, object]],
    expanded: list[dict[str, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    field_quality = Counter(str(row["field_quality"]) for row in rows)
    example_quality = Counter(str(row["example_quality"]) for row in rows)
    category_alignment = Counter(str(row["category_alignment"]) for row in rows)
    match_field = Counter(row["match_field"] for row in expanded)
    match_quality = Counter(row["match_quality"] for row in expanded)
    indexed = {str(row["raw"]): row for row in rows}
    risk_lines = []
    for raw in ("hit", "shot", "gun", "ring", "whoosh"):
        row = indexed.get(raw)
        risk_lines.append(
            (
                f"- {raw}: approved_for_ai={row['approved_for_ai']}; "
                f"flags={row.get('qa_flags') or 'none'}"
            )
            if row
            else f"- {raw}: not present"
        )
    lines = [
        "# BOOM Evidence Expansion Report",
        "",
        f"- total candidate rows: `{summary.total_candidate_rows}`",
        f"- expanded evidence rows: `{summary.expanded_evidence_rows}`",
        (
            "- average examples per candidate: "
            f"`{summary.average_examples_per_candidate:.2f}`"
        ),
        (
            "- before approved_for_ai count: "
            f"`{summary.before_approved_for_ai_count}`"
        ),
        (
            "- after approved_for_ai count: "
            f"`{summary.after_approved_for_ai_count}`"
        ),
        "- canonical_tokens.csv changed: `no`",
        "- AI invoked: `no`",
        "- automatic promotion: `no`",
        "",
        "## Match field distribution",
        "",
        *_named_distribution_lines(match_field),
        "",
        "## Match quality distribution",
        "",
        *_named_distribution_lines(match_quality),
        "",
        "## Field quality distribution",
        "",
        *_named_distribution_lines(field_quality),
        "",
        "## Example quality distribution",
        "",
        *_named_distribution_lines(example_quality),
        "",
        "## Category alignment distribution",
        "",
        *_named_distribution_lines(category_alignment),
        "",
        "## High-risk token decision",
        "",
        *risk_lines,
        "",
        "## Canonical token guard",
        "",
        (
            "- canonical_tokens_sha256_before: "
            f"`{summary.canonical_tokens_sha256_before}`"
        ),
        (
            "- canonical_tokens_sha256_after: "
            f"`{summary.canonical_tokens_sha256_after}`"
        ),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _named_distribution_lines(counts: Counter[str]) -> list[str]:
    if not counts:
        return ["- none"]
    return [f"- {key}: `{counts[key]}`" for key in sorted(counts)]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate-evidence", type=Path, default=DEFAULT_CANDIDATE_EVIDENCE
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--max-examples", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        summary = expand_candidate_evidence(
            args.candidate_evidence,
            args.db,
            args.output_dir,
            args.report,
            args.canonical,
            max_examples_per_candidate=args.max_examples,
        )
    except (FileNotFoundError, ValueError, RuntimeError, sqlite3.DatabaseError) as exc:
        parser.error(str(exc))
    print(
        f"candidates={summary.total_candidate_rows} "
        f"expanded_examples={summary.expanded_evidence_rows} "
        f"approved_before={summary.before_approved_for_ai_count} "
        f"approved_after={summary.after_approved_for_ai_count} "
        f"canonical_changed={str(summary.canonical_tokens_changed).lower()} "
        "ai_invoked=no promote=no"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
