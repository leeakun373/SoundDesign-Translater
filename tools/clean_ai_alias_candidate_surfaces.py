#!/usr/bin/env python3
"""Clean Chinese alias surface suffixes before promotion planning."""

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

from fxengine.canonical_db import (  # noqa: E402
    CANONICAL_COLUMNS,
    DEFAULT_CANONICAL_PATH,
    load_canonical_rows,
)
from tools.build_ai_alias_candidate_review_intake import INTAKE_COLUMNS  # noqa: E402

DEFAULT_INPUT_CSV = (
    ROOT / "exports" / "ai_alias_prompt_pack" / "ai_alias_candidates_review_intake.csv"
)
DEFAULT_OUTPUT_CSV = (
    ROOT / "exports" / "ai_alias_prompt_pack" / "ai_alias_candidates_surface_cleaned.csv"
)
DEFAULT_REPORT = ROOT / "reports" / "ai_alias_candidate_surface_cleanup_report.md"

SURFACE_SUFFIXES = ("声音", "音效", "声效", "声", "音")
SURFACE_ACTIONS = ("keep_raw", "replace_raw", "needs_review", "reject_surface")
SURFACE_EXTRA_COLUMNS = ("cleaned_raw", "surface_action", "surface_reason", "surface_risk")
SURFACE_CLEANED_COLUMNS = (*INTAKE_COLUMNS, *SURFACE_EXTRA_COLUMNS)

DOOR_EVENT_RAWS = {"开门声", "关门声"}
RING_TAIL_RAWS = {"余响", "回响声", "金属回荡"}
DESCRIPTIVE_ACTION_STEMS = {"表面摩擦", "重物撞击"}


@dataclass(frozen=True)
class SurfaceCleanupSummary:
    input_count: int
    output_count: int
    duplicate_dropped_count: int
    counts_by_surface_action: dict[str, int]
    counts_by_surface_risk: dict[str, int]
    replaced_raw_count: int
    needs_review_count: int
    reject_surface_count: int
    csv_path: str
    report_path: str
    canonical_tokens_sha256_before: str
    canonical_tokens_sha256_after: str
    canonical_tokens_changed: bool
    promote: bool = False
    ai_invoked: bool = False


def clean_ai_alias_candidate_surfaces(
    input_csv: Path = DEFAULT_INPUT_CSV,
    output_csv: Path = DEFAULT_OUTPUT_CSV,
    report_path: Path = DEFAULT_REPORT,
    canonical_path: Path = DEFAULT_CANONICAL_PATH,
) -> SurfaceCleanupSummary:
    """Normalize alias surfaces for review; never edits canonical data or runtime state."""
    input_csv = Path(input_csv)
    output_csv = Path(output_csv)
    report_path = Path(report_path)
    canonical_path = Path(canonical_path)

    for path in (input_csv, canonical_path):
        if not path.is_file():
            raise FileNotFoundError(f"Required input not found: {path}")
    _require_distinct_output_paths(input_csv, output_csv, report_path, canonical_path)

    canonical_before = _sha256(canonical_path)
    existing_raws = _existing_canonical_raws(canonical_path)
    source_rows = _read_intake_rows(input_csv)
    cleaned_rows: list[dict[str, str]] = []
    duplicate_keys: set[tuple[str, str, str]] = set()
    duplicate_dropped = 0

    for row in source_rows:
        surface = _classify_surface(row, existing_raws=existing_raws)
        candidate = {**row, **surface}
        dedupe_key = (
            _effective_raw(candidate).casefold(),
            candidate["canonical"].casefold(),
            candidate["slot"].casefold(),
        )
        if dedupe_key in duplicate_keys:
            duplicate_dropped += 1
            continue
        duplicate_keys.add(dedupe_key)
        cleaned_rows.append(candidate)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(output_csv, cleaned_rows)

    canonical_after = _sha256(canonical_path)
    action_counts = Counter(row["surface_action"] for row in cleaned_rows)
    summary = SurfaceCleanupSummary(
        input_count=len(source_rows),
        output_count=len(cleaned_rows),
        duplicate_dropped_count=duplicate_dropped,
        counts_by_surface_action={action: action_counts[action] for action in SURFACE_ACTIONS},
        counts_by_surface_risk=_ordered_counts(cleaned_rows, "surface_risk", ("low", "medium", "high")),
        replaced_raw_count=action_counts["replace_raw"],
        needs_review_count=action_counts["needs_review"],
        reject_surface_count=action_counts["reject_surface"],
        csv_path=str(output_csv),
        report_path=str(report_path),
        canonical_tokens_sha256_before=canonical_before,
        canonical_tokens_sha256_after=canonical_after,
        canonical_tokens_changed=canonical_after != canonical_before,
    )
    if summary.canonical_tokens_changed:
        raise RuntimeError("canonical_tokens.csv changed while cleaning alias surfaces")
    _write_report(
        report_path,
        summary=summary,
        input_csv=input_csv,
        cleaned_rows=cleaned_rows,
        duplicate_dropped=duplicate_dropped,
    )
    return summary


def effective_raw(row: Mapping[str, str]) -> str:
    """Return the raw token decision/plan stages should prefer."""
    return _effective_raw(row)


def _effective_raw(row: Mapping[str, str]) -> str:
    action = row.get("surface_action", "")
    cleaned = row.get("cleaned_raw", "")
    if action == "replace_raw" and cleaned:
        return cleaned
    if action == "needs_review" and cleaned:
        return cleaned
    return row["raw"]


def _read_intake_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = set(INTAKE_COLUMNS) - fieldnames
        if missing:
            raise ValueError(f"{path} is missing intake columns: {', '.join(sorted(missing))}")
        return [
            {column: (source_row.get(column) or "").strip() for column in INTAKE_COLUMNS}
            for source_row in reader
        ]


def _existing_canonical_raws(canonical_path: Path) -> set[str]:
    return {row.raw.casefold() for row in load_canonical_rows(canonical_path)}


def _strip_sound_suffix(raw: str) -> tuple[str, str]:
    for suffix in SURFACE_SUFFIXES:
        if raw.endswith(suffix) and len(raw) > len(suffix):
            return raw[: -len(suffix)].strip(), suffix
    return raw, ""


def _classify_surface(
    row: Mapping[str, str],
    *,
    existing_raws: set[str],
) -> dict[str, str]:
    raw = row["raw"]
    canonical = row["canonical"]
    slot = row["slot"]

    if raw.casefold() in existing_raws:
        return _surface(
            raw,
            raw,
            "reject_surface",
            "existing_canonical_raw_conflict",
            "high",
        )

    if raw in DOOR_EVENT_RAWS and slot == "object":
        return _surface(
            raw,
            _strip_sound_suffix(raw)[0],
            "needs_review",
            "door_event_not_object",
            "medium",
        )
    if raw == "门轴吱响":
        return _surface(raw, raw, "needs_review", "hinge_squeak_event", "medium")
    if raw == "枪声":
        return _surface(raw, raw, "keep_raw", "shot_sound_concept", "high")
    if raw == "炮击声":
        cleaned, _suffix = _strip_sound_suffix(raw)
        return _surface(raw, cleaned, "needs_review", "shot_sound_concept", "high")
    if raw == "开火声":
        cleaned, _suffix = _strip_sound_suffix(raw)
        return _surface(raw, cleaned, "replace_raw", "weapon_fire_action", "high")
    if raw == "发射声":
        cleaned, _suffix = _strip_sound_suffix(raw)
        return _surface(raw, cleaned, "needs_review", "too_broad_weapon_action", "high")
    if raw == "振铃声":
        cleaned, _suffix = _strip_sound_suffix(raw)
        return _surface(raw, cleaned, "needs_review", "tonal_ring_surface", "medium")
    if raw in RING_TAIL_RAWS:
        return _surface(raw, raw, "needs_review", "tonal_tail_no_auto_promote", "medium")
    if raw == "拳击声":
        cleaned, _suffix = _strip_sound_suffix(raw)
        return _surface(raw, cleaned, "needs_review", "fight_specific_surface", "high")
    if slot == "object" and _object_slot_sound_event(raw):
        cleaned, _suffix = _strip_sound_suffix(raw)
        return _surface(
            raw,
            cleaned if cleaned != raw else raw,
            "needs_review",
            "object_slot_sound_event",
            "medium",
        )

    cleaned, suffix = _strip_sound_suffix(raw)
    if not suffix:
        return _surface(raw, raw, "keep_raw", "no_suffix", "low")

    if _semantic_class_would_change(raw, cleaned, canonical=canonical, slot=slot):
        return _surface(raw, raw, "keep_raw", "semantic_class_preserved", "medium")

    if slot == "action" and cleaned in DESCRIPTIVE_ACTION_STEMS:
        return _surface(raw, cleaned, "needs_review", "surface_too_descriptive", "medium")

    if slot == "action" and cleaned:
        surface = _surface(raw, cleaned, "replace_raw", f"strip_suffix_{suffix}", "low")
        return _apply_existing_raw_conflict(row["raw"], surface, existing_raws)

    return _surface(raw, raw, "keep_raw", "no_safe_surface_replace", "medium")


def _apply_existing_raw_conflict(
    raw: str,
    surface: dict[str, str],
    existing_raws: set[str],
) -> dict[str, str]:
    cleaned = surface["cleaned_raw"]
    if cleaned.casefold() in existing_raws:
        return _surface(
            raw,
            cleaned,
            "reject_surface",
            "existing_canonical_raw_conflict",
            "high",
        )
    return surface


def _semantic_class_would_change(
    raw: str,
    cleaned: str,
    *,
    canonical: str,
    slot: str,
) -> bool:
    if raw == "枪声" and cleaned == "枪":
        return True
    if raw in DOOR_EVENT_RAWS and slot == "object":
        return True
    if canonical == "Shot" and raw.endswith("声") and cleaned != raw and len(cleaned) <= 2:
        return raw != "开火声"
    return False


def _object_slot_sound_event(raw: str) -> bool:
    if raw in DOOR_EVENT_RAWS:
        return True
    if raw.endswith("晃动声"):
        return True
    return raw.endswith(("声", "响"))


def _surface(
    raw: str,
    cleaned_raw: str,
    action: str,
    reason: str,
    risk: str,
) -> dict[str, str]:
    if action not in SURFACE_ACTIONS:
        raise ValueError(f"invalid surface_action: {action}")
    if risk not in {"low", "medium", "high"}:
        raise ValueError(f"invalid surface_risk: {risk}")
    cleaned = cleaned_raw.strip() or raw
    return {
        "cleaned_raw": cleaned,
        "surface_action": action,
        "surface_reason": reason,
        "surface_risk": risk,
    }


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


def _ordered_counts(
    rows: list[dict[str, str]],
    field: str,
    order: tuple[str, ...],
) -> dict[str, int]:
    counts = Counter(row[field] for row in rows)
    return {value: counts[value] for value in order}


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SURFACE_CLEANED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_report(
    path: Path,
    *,
    summary: SurfaceCleanupSummary,
    input_csv: Path,
    cleaned_rows: list[dict[str, str]],
    duplicate_dropped: int,
) -> None:
    replaced_rows = [
        row for row in cleaned_rows if row["surface_action"] == "replace_raw"
    ]
    review_rows = [
        row for row in cleaned_rows if row["surface_action"] == "needs_review"
    ]
    lines = [
        "# AI Alias Candidate Surface Cleanup Report",
        "",
        "Surface cleanup only. No canonical overwrite, runtime activation, keep, or promotion.",
        "",
        f"- input_count: `{summary.input_count}`",
        f"- output_count: `{summary.output_count}`",
        f"- duplicate_dropped_count: `{duplicate_dropped}`",
        f"- replaced_raw_count: `{summary.replaced_raw_count}`",
        f"- needs_review_count: `{summary.needs_review_count}`",
        f"- reject_surface_count: `{summary.reject_surface_count}`",
        f"- canonical_tokens.csv changed: `{'yes' if summary.canonical_tokens_changed else 'no'}`",
        "- promote: `no`",
        "- AI invoked: `no`",
        f"- CSV: `{summary.csv_path}`",
        "",
        "## Surface action counts",
        "",
        *(
            f"- {action}: `{count}`"
            for action, count in summary.counts_by_surface_action.items()
        ),
        "",
        "## Surface risk counts",
        "",
        *(
            f"- {risk}: `{count}`"
            for risk, count in summary.counts_by_surface_risk.items()
        ),
        "",
        "## Replaced raw rows",
        "",
        *(
            f"- {row['raw']} -> {row['cleaned_raw']} / {row['canonical']} / {row['surface_reason']}"
            for row in replaced_rows
        ),
        "",
        "## Needs review surface rows",
        "",
        *(
            f"- {row['raw']} / cleaned={row['cleaned_raw']} / {row['canonical']} / {row['surface_reason']}"
            for row in review_rows
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
        summary = clean_ai_alias_candidate_surfaces(
            args.input_csv,
            args.output_csv,
            args.report,
            args.canonical,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(
        f"input={summary.input_count} output={summary.output_count} "
        f"replace={summary.replaced_raw_count} review={summary.needs_review_count} "
        f"reject={summary.reject_surface_count} promote=no ai_invoked=no "
        f"canonical_changed={str(summary.canonical_tokens_changed).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
