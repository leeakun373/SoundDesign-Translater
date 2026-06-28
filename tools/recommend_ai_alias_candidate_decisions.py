#!/usr/bin/env python3
"""Recommend review decisions for AI alias candidates without promoting them."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fxengine.canonical_db import CANONICAL_COLUMNS, DEFAULT_CANONICAL_PATH  # noqa: E402


DEFAULT_INPUT_CSV = (
    ROOT / "exports" / "ai_alias_prompt_pack" / "ai_alias_candidates_review_intake.csv"
)
DEFAULT_OUTPUT_CSV = (
    ROOT
    / "exports"
    / "ai_alias_prompt_pack"
    / "ai_alias_candidates_decision_recommendations.csv"
)
DEFAULT_REPORT = ROOT / "reports" / "ai_alias_candidates_decision_recommendations_report.md"

INTAKE_COLUMNS = (
    *CANONICAL_COLUMNS,
    "review_batch",
    "review_risk",
    "review_action",
    "review_reason",
)
DECISION_COLUMNS = (
    *INTAKE_COLUMNS,
    "decision_recommendation",
    "decision_reason",
    "conflict_group",
)
DECISIONS = ("accept_candidate", "needs_review", "reject_candidate")
BATCHES = ("batch_safe", "batch_caution", "batch_weapon")
RING_TAIL_RAWS = {"余响", "回响声", "金属回荡"}


@dataclass(frozen=True)
class RecommendationSummary:
    total_count: int
    counts_by_decision: dict[str, int]
    conflict_group_count: int
    conflict_candidate_count: int
    counts_by_canonical: dict[str, dict[str, int]]
    counts_by_batch: dict[str, dict[str, int]]
    csv_path: str
    report_path: str
    has_keep: bool
    all_source_ai_candidate: bool
    all_priority_zero: bool
    canonical_tokens_sha256_before: str
    canonical_tokens_sha256_after: str
    canonical_tokens_changed: bool
    promote: bool = False


def recommend_ai_alias_candidate_decisions(
    input_csv: Path = DEFAULT_INPUT_CSV,
    output_csv: Path = DEFAULT_OUTPUT_CSV,
    report_path: Path = DEFAULT_REPORT,
    canonical_path: Path = DEFAULT_CANONICAL_PATH,
) -> RecommendationSummary:
    """Create a recommendation table; never edits canonical data or runtime state."""
    input_csv = Path(input_csv)
    output_csv = Path(output_csv)
    report_path = Path(report_path)
    canonical_path = Path(canonical_path)

    for path in (input_csv, canonical_path):
        if not path.is_file():
            raise FileNotFoundError(f"Required input not found: {path}")
    _require_distinct_output_paths(input_csv, output_csv, report_path, canonical_path)

    canonical_before = _sha256(canonical_path)
    intake_rows = _read_intake_rows(input_csv)
    conflict_groups = _build_conflict_groups(intake_rows)
    decision_rows = [
        _recommend_row(row, conflict_group=conflict_groups.get(_raw_key(row["raw"]), ""))
        for row in intake_rows
    ]

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(output_csv, decision_rows)

    canonical_after = _sha256(canonical_path)
    counts_by_decision = Counter(row["decision_recommendation"] for row in decision_rows)
    summary = RecommendationSummary(
        total_count=len(decision_rows),
        counts_by_decision={decision: counts_by_decision[decision] for decision in DECISIONS},
        conflict_group_count=len(set(conflict_groups.values())),
        conflict_candidate_count=sum(bool(row["conflict_group"]) for row in decision_rows),
        counts_by_canonical=_grouped_decision_counts(decision_rows, "canonical"),
        counts_by_batch=_grouped_decision_counts(decision_rows, "review_batch", order=BATCHES),
        csv_path=str(output_csv),
        report_path=str(report_path),
        has_keep=any(row["review_status"] == "keep" for row in decision_rows),
        all_source_ai_candidate=all(row["source"] == "ai_candidate" for row in decision_rows),
        all_priority_zero=all(row["priority"] == "0" for row in decision_rows),
        canonical_tokens_sha256_before=canonical_before,
        canonical_tokens_sha256_after=canonical_after,
        canonical_tokens_changed=canonical_after != canonical_before,
    )
    if summary.canonical_tokens_changed:
        raise RuntimeError("canonical_tokens.csv changed while recommending candidate decisions")
    _write_report(report_path, summary=summary, input_csv=input_csv, rows=decision_rows)
    return summary


def _read_intake_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = set(INTAKE_COLUMNS) - fieldnames
        if missing:
            raise ValueError(f"{path} is missing intake columns: {', '.join(sorted(missing))}")
        rows = [
            {column: (source_row.get(column) or "").strip() for column in INTAKE_COLUMNS}
            for source_row in reader
        ]
    for row_number, row in enumerate(rows, 2):
        _validate_intake_row(row, row_number=row_number)
    return rows


def _validate_intake_row(row: Mapping[str, str], *, row_number: int) -> None:
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
    if row["review_action"] != "pending":
        raise ValueError(f"row {row_number}: review_action must be pending")
    if row["review_batch"] not in BATCHES:
        raise ValueError(f"row {row_number}: invalid review_batch")
    if row["review_risk"] not in {"low", "medium", "high"}:
        raise ValueError(f"row {row_number}: invalid review_risk")


def _build_conflict_groups(rows: list[dict[str, str]]) -> dict[str, str]:
    canonicals_by_raw: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        canonicals_by_raw[_raw_key(row["raw"])].add(row["canonical"].casefold())
    conflict_keys = sorted(
        raw_key for raw_key, canonicals in canonicals_by_raw.items() if len(canonicals) > 1
    )
    return {
        raw_key: f"raw_conflict_{index:03d}"
        for index, raw_key in enumerate(conflict_keys, 1)
    }


def _recommend_row(row: Mapping[str, str], *, conflict_group: str) -> dict[str, str]:
    recommendation, reasons = _default_recommendation(row)
    raw = row["raw"]
    canonical = row["canonical"]

    if row["review_reason"]:
        reasons.append(row["review_reason"])
    if conflict_group:
        recommendation = _require_review(recommendation)
        reasons.append("raw_multi_canonical_conflict")
    if row["slot"] == "object" and _looks_like_sound_event(raw):
        recommendation = _require_review(recommendation)
        reasons.append("object_slot_sound_event")
    if canonical == "Gun" and raw == "枪炮":
        recommendation = _require_review(recommendation)
        reasons.append("broad_weapon_term")
    if canonical == "Shot" and raw == "发射声":
        recommendation = _require_review(recommendation)
        reasons.append("too_broad_weapon_action")
    if canonical == "Ring" and raw in RING_TAIL_RAWS:
        recommendation = _require_review(recommendation)
        reasons.append("tonal_tail_or_reverb_possible")
    if canonical == "Hit" and "拳击声" in raw:
        reasons.append("fight_specific")
    if canonical == "Hit" and "命中" in raw:
        recommendation = "reject_candidate"
        reasons.append("forbidden_hit_literal_match")

    return {
        **{column: row[column] for column in INTAKE_COLUMNS},
        "decision_recommendation": recommendation,
        "decision_reason": ";".join(dict.fromkeys(reasons)),
        "conflict_group": conflict_group,
    }


def _default_recommendation(row: Mapping[str, str]) -> tuple[str, list[str]]:
    if row["review_batch"] == "batch_safe" and row["review_risk"] == "low":
        return "accept_candidate", ["safe_low_risk"]
    if row["review_batch"] == "batch_safe":
        return "needs_review", ["safe_medium_risk"]
    if row["review_batch"] == "batch_caution":
        return "needs_review", ["caution_batch_default"]
    return "needs_review", ["weapon_batch_default"]


def _require_review(recommendation: str) -> str:
    return "reject_candidate" if recommendation == "reject_candidate" else "needs_review"


def _looks_like_sound_event(raw: str) -> bool:
    return raw.endswith(("声", "响"))


def _raw_key(raw: str) -> str:
    return raw.strip().casefold()


def _grouped_decision_counts(
    rows: list[dict[str, str]],
    field: str,
    *,
    order: tuple[str, ...] | None = None,
) -> dict[str, dict[str, int]]:
    keys = order or tuple(sorted({row[field] for row in rows}))
    result: dict[str, dict[str, int]] = {}
    for key in keys:
        counts = Counter(
            row["decision_recommendation"] for row in rows if row[field] == key
        )
        result[key] = {decision: counts[decision] for decision in DECISIONS}
    return result


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
        raise ValueError("output CSV must not overwrite the intake CSV")
    if resolved["output CSV"] == resolved["report"]:
        raise ValueError("output CSV and report must use different paths")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DECISION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _format_decision_counts(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{decision}={counts[decision]}" for decision in DECISIONS)


def _write_report(
    path: Path,
    *,
    summary: RecommendationSummary,
    input_csv: Path,
    rows: list[dict[str, str]],
) -> None:
    needs_review_rows = [
        row for row in rows if row["decision_recommendation"] == "needs_review"
    ]
    lines = [
        "# AI Alias Candidate Decision Recommendations Report",
        "",
        "Recommendation table only. No canonical overwrite, runtime activation, keep, or promotion.",
        "",
        f"- total_count: `{summary.total_count}`",
        *(
            f"- {decision}: `{count}`"
            for decision, count in summary.counts_by_decision.items()
        ),
        f"- conflict_group_count: `{summary.conflict_group_count}`",
        f"- conflict_candidate_count: `{summary.conflict_candidate_count}`",
        f"- keep appears: `{'yes' if summary.has_keep else 'no'}`",
        f"- all_source_ai_candidate: `{str(summary.all_source_ai_candidate).lower()}`",
        f"- all_priority_zero: `{str(summary.all_priority_zero).lower()}`",
        f"- canonical_tokens.csv changed: `{'yes' if summary.canonical_tokens_changed else 'no'}`",
        "- promote: `no`",
        f"- CSV: `{summary.csv_path}`",
        "",
        "## Decisions by canonical",
        "",
        *(
            f"- {canonical}: {_format_decision_counts(counts)}"
            for canonical, counts in summary.counts_by_canonical.items()
        ),
        "",
        "## Decisions by review batch",
        "",
        *(
            f"- {batch}: {_format_decision_counts(counts)}"
            for batch, counts in summary.counts_by_batch.items()
        ),
        "",
        "## Needs review",
        "",
        *(
            f"- {row['raw']} / {row['canonical']} / {row['decision_reason']}"
            + (f" / {row['conflict_group']}" if row["conflict_group"] else "")
            for row in needs_review_rows
        ),
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
        summary = recommend_ai_alias_candidate_decisions(
            args.input_csv,
            args.output_csv,
            args.report,
            args.canonical,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(
        f"total={summary.total_count} "
        f"accept={summary.counts_by_decision['accept_candidate']} "
        f"review={summary.counts_by_decision['needs_review']} "
        f"reject={summary.counts_by_decision['reject_candidate']} "
        f"conflicts={summary.conflict_group_count} promote=no "
        f"canonical_changed={str(summary.canonical_tokens_changed).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
