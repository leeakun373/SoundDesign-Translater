#!/usr/bin/env python3
"""Build a dry-run promote plan from AI alias decision recommendations."""

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
from tools.recommend_ai_alias_candidate_decisions import (  # noqa: E402
    DECISION_COLUMNS,
    DECISION_SURFACE_COLUMNS,
    SURFACE_EXTRA_COLUMNS,
    _require_distinct_output_paths,
    _sha256,
)


DEFAULT_INPUT_CSV = (
    ROOT
    / "exports"
    / "ai_alias_prompt_pack"
    / "ai_alias_candidates_decision_recommendations.csv"
)
DEFAULT_INPUT_V2_CSV = (
    ROOT
    / "exports"
    / "ai_alias_prompt_pack"
    / "ai_alias_candidates_decision_recommendations_v2.csv"
)
DEFAULT_OUTPUT_CSV = ROOT / "exports" / "ai_alias_prompt_pack" / "promote_plan_batch0.csv"
DEFAULT_OUTPUT_V2_CSV = ROOT / "exports" / "ai_alias_prompt_pack" / "promote_plan_batch0_v2.csv"
DEFAULT_REPORT = ROOT / "reports" / "ai_alias_promote_plan_batch0_report.md"
DEFAULT_REPORT_V2 = ROOT / "reports" / "ai_alias_promote_plan_batch0_v2_report.md"

BATCH0_ID = "batch0_dry_run"
BATCH0_V2_ID = "batch0_dry_run_v2"
PLAN_ACTION = "plan_only"
PLANNED_REVIEW_STATUS = "proposed_keep"
ROLLBACK_NOTE = "no runtime change; delete this plan row"

WEAPON_CANONICALS = {"Gun", "Shot", "Single Shot"}

PLAN_EXTRA_COLUMNS = (
    "review_batch",
    "review_risk",
    "decision_recommendation",
    "decision_reason",
    "batch_id",
    "plan_action",
    "canonical_sha256_before",
    "rollback_note",
)
PLAN_COLUMNS = (*CANONICAL_COLUMNS, *PLAN_EXTRA_COLUMNS)


@dataclass(frozen=True)
class PlanSummary:
    input_count: int
    planned_count: int
    skipped_count: int
    skip_reason_counts: dict[str, int]
    csv_path: str
    report_path: str
    has_keep: bool
    has_runtime_keep: bool
    all_plan_action_plan_only: bool
    all_batch_id_batch0: bool
    canonical_tokens_sha256_before: str
    canonical_tokens_sha256_after: str
    canonical_tokens_changed: bool
    promote: bool = False
    ai_invoked: bool = False


def plan_ai_alias_promotions(
    input_csv: Path = DEFAULT_INPUT_CSV,
    output_csv: Path = DEFAULT_OUTPUT_CSV,
    report_path: Path = DEFAULT_REPORT,
    canonical_path: Path = DEFAULT_CANONICAL_PATH,
    *,
    batch_id: str | None = None,
) -> PlanSummary:
    """Create a batch0 dry-run promote plan; never edits canonical data or runtime state."""
    input_csv = Path(input_csv)
    output_csv = Path(output_csv)
    report_path = Path(report_path)
    canonical_path = Path(canonical_path)
    resolved_batch_id = batch_id or _default_batch_id(output_csv)

    for path in (input_csv, canonical_path):
        if not path.is_file():
            raise FileNotFoundError(f"Required input not found: {path}")
    _require_distinct_output_paths(input_csv, output_csv, report_path, canonical_path)

    canonical_before = _sha256(canonical_path)
    decision_rows, surface_mode = _read_decision_rows(input_csv)
    skip_reasons: Counter[str] = Counter()
    planned_rows: list[dict[str, str]] = []

    for row in decision_rows:
        skip_reason = _skip_reason(row)
        if skip_reason:
            skip_reasons[skip_reason] += 1
            continue
        planned_rows.append(
            _build_plan_row(
                row,
                canonical_sha256_before=canonical_before,
                batch_id=resolved_batch_id,
            )
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(output_csv, planned_rows)

    canonical_after = _sha256(canonical_path)
    summary = PlanSummary(
        input_count=len(decision_rows),
        planned_count=len(planned_rows),
        skipped_count=len(decision_rows) - len(planned_rows),
        skip_reason_counts=dict(sorted(skip_reasons.items())),
        csv_path=str(output_csv),
        report_path=str(report_path),
        has_keep=any(row["review_status"] == "keep" for row in decision_rows),
        has_runtime_keep=any(row["review_status"] == "keep" for row in planned_rows),
        all_plan_action_plan_only=all(row["plan_action"] == PLAN_ACTION for row in planned_rows),
        all_batch_id_batch0=all(row["batch_id"] == resolved_batch_id for row in planned_rows),
        canonical_tokens_sha256_before=canonical_before,
        canonical_tokens_sha256_after=canonical_after,
        canonical_tokens_changed=canonical_after != canonical_before,
    )
    if summary.has_keep:
        raise ValueError("decision input must not contain review_status=keep")
    if summary.has_runtime_keep:
        raise ValueError("plan output must not contain review_status=keep")
    if summary.canonical_tokens_changed:
        raise RuntimeError("canonical_tokens.csv changed while planning promotions")
    _write_report(
        report_path,
        summary=summary,
        input_csv=input_csv,
        planned_rows=planned_rows,
        batch_id=resolved_batch_id,
        surface_mode=surface_mode,
    )
    return summary


def _default_batch_id(output_csv: Path) -> str:
    if output_csv.name.endswith("_v2.csv"):
        return BATCH0_V2_ID
    return BATCH0_ID


def _read_decision_rows(path: Path) -> tuple[list[dict[str, str]], bool]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        surface_mode = SURFACE_EXTRA_COLUMNS[0] in fieldnames
        required = DECISION_SURFACE_COLUMNS if surface_mode else DECISION_COLUMNS
        missing = set(required) - fieldnames
        if missing:
            raise ValueError(f"{path} is missing decision columns: {', '.join(sorted(missing))}")
        return [
            {column: (source_row.get(column) or "").strip() for column in required}
            for source_row in reader
        ], surface_mode


def _skip_reason(row: Mapping[str, str]) -> str | None:
    if row["decision_recommendation"] != "accept_candidate":
        return "not_accept_candidate"
    if row["conflict_group"]:
        return "has_conflict_group"
    if row["canonical"] in WEAPON_CANONICALS:
        return "weapon_canonical"
    if row["review_batch"] != "batch_safe":
        return "not_batch_safe"
    return None


def _build_plan_row(
    row: Mapping[str, str],
    *,
    canonical_sha256_before: str,
    batch_id: str,
) -> dict[str, str]:
    note = row["note"]
    if row.get("original_raw") and row["original_raw"] != row["raw"]:
        note = f"{note};surface_from={row['original_raw']}"
    return {
        "raw": row["raw"],
        "canonical": row["canonical"],
        "slot": row["slot"],
        "lang": row["lang"],
        "priority": "0",
        "rule_type": row["rule_type"],
        "review_status": PLANNED_REVIEW_STATUS,
        "ambiguity": row["ambiguity"],
        "tags": row["tags"],
        "source": "ai_candidate_planned_promotion",
        "note": note,
        "review_batch": row["review_batch"],
        "review_risk": row["review_risk"],
        "decision_recommendation": row["decision_recommendation"],
        "decision_reason": row["decision_reason"],
        "batch_id": batch_id,
        "plan_action": PLAN_ACTION,
        "canonical_sha256_before": canonical_sha256_before,
        "rollback_note": ROLLBACK_NOTE,
    }


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PLAN_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_report(
    path: Path,
    *,
    summary: PlanSummary,
    input_csv: Path,
    planned_rows: list[dict[str, str]],
    batch_id: str,
    surface_mode: bool,
) -> None:
    title = "AI Alias Promote Plan Batch 0 v2 Report" if batch_id == BATCH0_V2_ID else "AI Alias Promote Plan Batch 0 Report"
    lines = [
        f"# {title}",
        "",
        "This is a dry-run plan only. No runtime row was added.",
        "",
        f"- input_count: `{summary.input_count}`",
        f"- planned_count: `{summary.planned_count}`",
        f"- skipped_count: `{summary.skipped_count}`",
        f"- surface_input: `{str(surface_mode).lower()}`",
        f"- batch_id: `{batch_id}`",
        f"- canonical_tokens.csv changed: `{'yes' if summary.canonical_tokens_changed else 'no'}`",
        "- promote: `no`",
        "- AI invoked: `no`",
        f"- CSV: `{summary.csv_path}`",
        "",
        "## Skip reason counts",
        "",
        *(
            f"- {reason}: `{count}`"
            for reason, count in summary.skip_reason_counts.items()
        ),
        "",
        "## Planned rows",
        "",
        *(
            f"- {row['raw']} -> {row['canonical']} / {row['slot']} / {row['review_status']}"
            for row in planned_rows
        ),
        "",
        "## Plan guardrails",
        "",
        f"- all plan_action={PLAN_ACTION}: `{str(summary.all_plan_action_plan_only).lower()}`",
        f"- all batch_id={batch_id}: `{str(summary.all_batch_id_batch0).lower()}`",
        f"- review_status uses `{PLANNED_REVIEW_STATUS}` only (not runtime keep)",
        "- source uses `ai_candidate_planned_promotion` (not yet in runtime)",
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT_CSV)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL_PATH)
    parser.add_argument("--batch-id", type=str, default=None)
    args = parser.parse_args(argv)
    try:
        summary = plan_ai_alias_promotions(
            args.input_csv,
            args.output_csv,
            args.report,
            args.canonical,
            batch_id=args.batch_id,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(
        f"input={summary.input_count} planned={summary.planned_count} "
        f"skipped={summary.skipped_count} promote=no ai_invoked=no "
        f"canonical_changed={str(summary.canonical_tokens_changed).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
