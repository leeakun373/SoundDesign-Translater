#!/usr/bin/env python3
"""Build a review-only intake queue from imported AI alias candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fxengine.canonical_db import CANONICAL_COLUMNS, DEFAULT_CANONICAL_PATH  # noqa: E402


DEFAULT_INPUT_CSV = (
    ROOT / "exports" / "ai_alias_prompt_pack" / "ai_alias_candidates_review_real.csv"
)
DEFAULT_OUTPUT_CSV = (
    ROOT / "exports" / "ai_alias_prompt_pack" / "ai_alias_candidates_review_intake.csv"
)
DEFAULT_REPORT = ROOT / "reports" / "ai_alias_candidates_review_intake_report.md"

INTAKE_COLUMNS = (*CANONICAL_COLUMNS, "review_batch", "review_risk", "review_action", "review_reason")

BATCH_CANONICALS = {
    "batch_safe": {"Impact", "Friction", "Chain", "Door", "Drop"},
    "batch_caution": {"Hit", "Squeak", "Crack", "Ring"},
    "batch_weapon": {"Gun", "Shot", "Single Shot"},
}

SPECIAL_REASONS = {
    "Hit": "ambiguous_with_impact_knock_punch",
    "Squeak": "category_pollution_possible",
    "Crack": "broad_material_spread",
    "Ring": "tonal_ambience_possible",
    "Gun": "weapon_object_high_risk",
    "Shot": "weapon_action_high_risk",
    "Single Shot": "phrase_weapon_high_risk",
}

DEFAULT_REASONS = {
    "batch_safe": "standard_alias_review",
    "batch_caution": "caution_alias_review",
    "batch_weapon": "weapon_alias_review",
}


@dataclass(frozen=True)
class IntakeSummary:
    intake_count: int
    counts_by_batch: dict[str, int]
    counts_by_risk: dict[str, int]
    counts_by_canonical: dict[str, int]
    csv_path: str
    report_path: str
    has_keep: bool
    all_source_ai_candidate: bool
    all_priority_zero: bool
    all_actions_pending: bool
    canonical_tokens_sha256_before: str
    canonical_tokens_sha256_after: str
    canonical_tokens_changed: bool
    promote: bool = False


def build_ai_alias_candidate_review_intake(
    input_csv: Path = DEFAULT_INPUT_CSV,
    output_csv: Path = DEFAULT_OUTPUT_CSV,
    report_path: Path = DEFAULT_REPORT,
    canonical_path: Path = DEFAULT_CANONICAL_PATH,
) -> IntakeSummary:
    """Create an intake queue without changing canonical data or runtime state."""
    input_csv = Path(input_csv)
    output_csv = Path(output_csv)
    report_path = Path(report_path)
    canonical_path = Path(canonical_path)

    for path in (input_csv, canonical_path):
        if not path.is_file():
            raise FileNotFoundError(f"Required input not found: {path}")
    _require_distinct_output_paths(input_csv, output_csv, report_path, canonical_path)

    canonical_before = _sha256(canonical_path)
    source_rows = _read_source_rows(input_csv)
    intake_rows = [_build_intake_row(row, row_number=index) for index, row in enumerate(source_rows, 2)]

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(output_csv, intake_rows)

    canonical_after = _sha256(canonical_path)
    summary = IntakeSummary(
        intake_count=len(intake_rows),
        counts_by_batch=_ordered_counts(
            intake_rows,
            "review_batch",
            ("batch_safe", "batch_caution", "batch_weapon"),
        ),
        counts_by_risk=_ordered_counts(intake_rows, "review_risk", ("low", "medium", "high")),
        counts_by_canonical=dict(sorted(Counter(row["canonical"] for row in intake_rows).items())),
        csv_path=str(output_csv),
        report_path=str(report_path),
        has_keep=any(row["review_status"] == "keep" for row in intake_rows),
        all_source_ai_candidate=all(row["source"] == "ai_candidate" for row in intake_rows),
        all_priority_zero=all(row["priority"] == "0" for row in intake_rows),
        all_actions_pending=all(row["review_action"] == "pending" for row in intake_rows),
        canonical_tokens_sha256_before=canonical_before,
        canonical_tokens_sha256_after=canonical_after,
        canonical_tokens_changed=canonical_after != canonical_before,
    )
    if summary.canonical_tokens_changed:
        raise RuntimeError("canonical_tokens.csv changed while building review intake")
    _write_report(report_path, summary=summary, input_csv=input_csv)
    return summary


def _read_source_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = set(CANONICAL_COLUMNS) - fieldnames
        if missing:
            raise ValueError(f"{path} is missing canonical columns: {', '.join(sorted(missing))}")
        return [
            {column: (source_row.get(column) or "").strip() for column in CANONICAL_COLUMNS}
            for source_row in reader
        ]


def _require_distinct_output_paths(
    input_csv: Path,
    output_csv: Path,
    report_path: Path,
    canonical_path: Path,
) -> None:
    resolved = {
        "input CSV": input_csv.resolve(),
        "output CSV": output_csv.resolve(),
        "report": report_path.resolve(),
        "canonical CSV": canonical_path.resolve(),
    }
    if resolved["output CSV"] == resolved["canonical CSV"]:
        raise ValueError("output CSV must not overwrite canonical_tokens.csv")
    if resolved["report"] == resolved["canonical CSV"]:
        raise ValueError("report must not overwrite canonical_tokens.csv")
    if resolved["output CSV"] == resolved["input CSV"]:
        raise ValueError("output CSV must not overwrite the intake source CSV")
    if resolved["output CSV"] == resolved["report"]:
        raise ValueError("output CSV and report must use different paths")


def _build_intake_row(source_row: Mapping[str, str], *, row_number: int) -> dict[str, str]:
    _validate_source_row(source_row, row_number=row_number)
    canonical = source_row["canonical"]
    review_batch = _review_batch(canonical)
    return {
        **{column: source_row[column] for column in CANONICAL_COLUMNS},
        "review_batch": review_batch,
        "review_risk": _review_risk(review_batch, source_row["ambiguity"]),
        "review_action": "pending",
        "review_reason": SPECIAL_REASONS.get(canonical, DEFAULT_REASONS[review_batch]),
    }


def _validate_source_row(row: Mapping[str, str], *, row_number: int) -> None:
    if not row["raw"]:
        raise ValueError(f"row {row_number}: raw must not be empty")
    if not row["canonical"]:
        raise ValueError(f"row {row_number}: canonical must not be empty")
    if row["review_status"] != "review":
        raise ValueError(f"row {row_number}: review_status must be review")
    if row["source"] != "ai_candidate":
        raise ValueError(f"row {row_number}: source must be ai_candidate")
    if row["priority"] != "0":
        raise ValueError(f"row {row_number}: priority must be 0")
    _review_batch(row["canonical"])


def _review_batch(canonical: str) -> str:
    for batch, canonicals in BATCH_CANONICALS.items():
        if canonical in canonicals:
            return batch
    raise ValueError(f"canonical is not assigned to an intake batch: {canonical}")


def _review_risk(review_batch: str, ambiguity: str) -> str:
    if review_batch == "batch_safe":
        return "low" if ambiguity == "low" else "medium"
    if review_batch == "batch_caution":
        return "high" if ambiguity == "high" else "medium"
    return "high"


def _ordered_counts(
    rows: list[dict[str, str]],
    field: str,
    order: tuple[str, ...],
) -> dict[str, int]:
    counts = Counter(row[field] for row in rows)
    return {value: counts[value] for value in order}


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INTAKE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_report(path: Path, *, summary: IntakeSummary, input_csv: Path) -> None:
    lines = [
        "# AI Alias Candidate Review Intake Report",
        "",
        "Review intake only. No canonical overwrite, runtime activation, keep, or promotion.",
        "",
        f"- intake_count: `{summary.intake_count}`",
        f"- keep appears: `{'yes' if summary.has_keep else 'no'}`",
        f"- all_source_ai_candidate: `{str(summary.all_source_ai_candidate).lower()}`",
        f"- all_priority_zero: `{str(summary.all_priority_zero).lower()}`",
        f"- all_review_action_pending: `{str(summary.all_actions_pending).lower()}`",
        f"- canonical_tokens.csv changed: `{'yes' if summary.canonical_tokens_changed else 'no'}`",
        f"- promote: `no`",
        f"- CSV: `{summary.csv_path}`",
        "",
        "## Counts by review batch",
        "",
        *(f"- {batch}: `{count}`" for batch, count in summary.counts_by_batch.items()),
        "",
        "## Counts by review risk",
        "",
        *(f"- {risk}: `{count}`" for risk, count in summary.counts_by_risk.items()),
        "",
        "## Counts by canonical",
        "",
        *(f"- {canonical}: `{count}`" for canonical, count in summary.counts_by_canonical.items()),
        "",
        "## Inputs",
        "",
        f"- `{input_csv}`",
        "",
        "## Canonical token guard",
        "",
        f"- canonical_tokens_sha256_before: `{summary.canonical_tokens_sha256_before}`",
        f"- canonical_tokens_sha256_after: `{summary.canonical_tokens_sha256_after}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT_CSV)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL_PATH)
    args = parser.parse_args(argv)
    try:
        summary = build_ai_alias_candidate_review_intake(
            args.input_csv,
            args.output_csv,
            args.report,
            args.canonical,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(
        f"intake={summary.intake_count} "
        f"safe={summary.counts_by_batch['batch_safe']} "
        f"caution={summary.counts_by_batch['batch_caution']} "
        f"weapon={summary.counts_by_batch['batch_weapon']} "
        f"keep={str(summary.has_keep).lower()} promote=no "
        f"canonical_changed={str(summary.canonical_tokens_changed).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
