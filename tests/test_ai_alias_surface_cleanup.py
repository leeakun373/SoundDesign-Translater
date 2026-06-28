"""Chinese alias surface cleanup stays review-only and preserves canonical hash."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

from fxengine.canonical_db import CANONICAL_COLUMNS, DEFAULT_CANONICAL_PATH
from tools.build_ai_alias_candidate_review_intake import INTAKE_COLUMNS
from tools.clean_ai_alias_candidate_surfaces import (
    SURFACE_CLEANED_COLUMNS,
    clean_ai_alias_candidate_surfaces,
    effective_raw,
)
from tools.plan_ai_alias_promotions import BATCH0_V2_ID, plan_ai_alias_promotions
from tools.recommend_ai_alias_candidate_decisions import (
    DECISION_SURFACE_COLUMNS,
    recommend_ai_alias_candidate_decisions,
)


def _intake_row(
    raw: str,
    canonical: str,
    *,
    slot: str | None = None,
    batch: str | None = None,
    risk: str | None = None,
    review_reason: str = "standard_alias_review",
) -> dict[str, str]:
    batch_by_canonical = {
        "Impact": "batch_safe",
        "Friction": "batch_safe",
        "Chain": "batch_safe",
        "Door": "batch_safe",
        "Drop": "batch_safe",
        "Hit": "batch_caution",
        "Squeak": "batch_caution",
        "Crack": "batch_caution",
        "Ring": "batch_caution",
        "Gun": "batch_weapon",
        "Shot": "batch_weapon",
        "Single Shot": "batch_weapon",
    }
    review_batch = batch or batch_by_canonical[canonical]
    review_risk = risk or (
        "low" if review_batch == "batch_safe" else "high" if review_batch == "batch_weapon" else "medium"
    )
    return {
        "raw": raw,
        "canonical": canonical,
        "slot": slot or ("object" if canonical in {"Gun", "Chain", "Door"} else "action"),
        "lang": "zh",
        "priority": "0",
        "rule_type": "alias",
        "review_status": "review",
        "ambiguity": review_risk,
        "tags": "test",
        "source": "ai_candidate",
        "note": "surface cleanup test",
        "review_batch": review_batch,
        "review_risk": review_risk,
        "review_action": "pending",
        "review_reason": review_reason,
    }


def _write_intake(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INTAKE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _read_surface_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _run_cleanup(tmp_path: Path, rows: list[dict[str, str]]):
    tmp_path.mkdir(parents=True, exist_ok=True)
    input_csv = tmp_path / "intake.csv"
    output_csv = tmp_path / "surface_cleaned.csv"
    report_path = tmp_path / "cleanup_report.md"
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    _write_intake(input_csv, rows)
    summary = clean_ai_alias_candidate_surfaces(
        input_csv,
        output_csv,
        report_path,
        canonical_path,
    )
    return summary, output_csv, report_path, canonical_path, input_csv


def _row_by_raw(rows: list[dict[str, str]], raw: str) -> dict[str, str]:
    return next(row for row in rows if row["raw"] == raw)


@pytest.mark.parametrize(
    ("raw", "expected_cleaned", "expected_action"),
    [
        ("摩擦声", "摩擦", "reject_surface"),
        ("擦蹭声", "擦蹭", "replace_raw"),
        ("磨蹭声", "磨蹭", "replace_raw"),
    ],
)
def test_friction_suffix_cleanup(
    tmp_path: Path,
    raw: str,
    expected_cleaned: str,
    expected_action: str,
) -> None:
    _, output_csv, _, _, _ = _run_cleanup(tmp_path, [_intake_row(raw, "Friction")])
    row = _row_by_raw(_read_surface_rows(output_csv), raw)
    assert row["cleaned_raw"] == expected_cleaned
    assert row["surface_action"] == expected_action


def test_surface_friction_alias_is_rejected_when_canonical_raw_exists(tmp_path: Path) -> None:
    _, output_csv, _, _, _ = _run_cleanup(tmp_path, [_intake_row("摩擦声", "Friction")])
    row = _row_by_raw(_read_surface_rows(output_csv), "摩擦声")
    assert row["surface_action"] == "reject_surface"
    assert row["surface_reason"] == "existing_canonical_raw_conflict"


def test_descriptive_surface_friction_alias_needs_review(tmp_path: Path) -> None:
    _, output_csv, _, _, _ = _run_cleanup(
        tmp_path,
        [_intake_row("表面摩擦音", "Friction")],
    )
    row = _row_by_raw(_read_surface_rows(output_csv), "表面摩擦音")
    assert row["cleaned_raw"] == "表面摩擦"
    assert row["surface_action"] == "needs_review"
    assert row["surface_reason"] == "surface_too_descriptive"


def test_gunshot_keeps_raw_not_gun_object(tmp_path: Path) -> None:
    _, output_csv, _, _, _ = _run_cleanup(tmp_path, [_intake_row("枪声", "Shot")])
    row = _row_by_raw(_read_surface_rows(output_csv), "枪声")
    assert row["cleaned_raw"] == "枪声"
    assert row["surface_action"] == "keep_raw"
    assert row["cleaned_raw"] != "枪"


def test_door_open_sound_does_not_become_door_object(tmp_path: Path) -> None:
    _, output_csv, _, _, _ = _run_cleanup(
        tmp_path,
        [_intake_row("开门声", "Door", slot="object")],
    )
    row = _row_by_raw(_read_surface_rows(output_csv), "开门声")
    assert row["surface_action"] == "needs_review"
    assert row["surface_reason"] == "door_event_not_object"
    assert row["cleaned_raw"] != "门"


def test_chain_sound_object_slot_needs_review(tmp_path: Path) -> None:
    _, output_csv, _, _, _ = _run_cleanup(
        tmp_path,
        [_intake_row("链条声", "Chain", slot="object")],
    )
    row = _row_by_raw(_read_surface_rows(output_csv), "链条声")
    assert row["surface_action"] == "needs_review"
    assert row["surface_reason"] == "object_slot_sound_event"


def test_shot_launch_action_needs_review(tmp_path: Path) -> None:
    _, output_csv, _, _, _ = _run_cleanup(tmp_path, [_intake_row("发射声", "Shot")])
    row = _row_by_raw(_read_surface_rows(output_csv), "发射声")
    assert row["surface_action"] == "needs_review"
    assert row["surface_reason"] == "too_broad_weapon_action"


def test_cleaned_raw_duplicate_is_dropped(tmp_path: Path) -> None:
    summary, output_csv, report_path, _, _ = _run_cleanup(
        tmp_path,
        [
            _intake_row("擦蹭声", "Friction"),
            _intake_row("擦蹭声", "Friction"),
        ],
    )
    rows = _read_surface_rows(output_csv)
    assert summary.output_count == 1
    assert summary.duplicate_dropped_count == 1
    assert "duplicate_dropped_count: `1`" in report_path.read_text(encoding="utf-8")
    assert len(rows) == 1


def test_surface_cleanup_does_not_change_canonical_hash(tmp_path: Path) -> None:
    summary, _, report_path, canonical_path, input_csv = _run_cleanup(
        tmp_path,
        [_intake_row("擦蹭声", "Friction")],
    )
    before = hashlib.sha256(DEFAULT_CANONICAL_PATH.read_bytes()).hexdigest().upper()
    after = hashlib.sha256(canonical_path.read_bytes()).hexdigest().upper()
    assert before == after
    assert summary.canonical_tokens_changed is False
    assert summary.promote is False
    assert summary.ai_invoked is False
    assert "promote: `no`" in report_path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="must not overwrite canonical_tokens.csv"):
        clean_ai_alias_candidate_surfaces(
            input_csv,
            canonical_path,
            report_path,
            canonical_path,
        )


def test_surface_needs_review_blocks_accept_in_decision_v2(tmp_path: Path) -> None:
    _, surface_csv, _, canonical_path, _ = _run_cleanup(
        tmp_path,
        [_intake_row("表面摩擦音", "Friction")],
    )
    decision_csv = tmp_path / "decisions_v2.csv"
    report_path = tmp_path / "decision_v2_report.md"
    summary = recommend_ai_alias_candidate_decisions(
        surface_csv,
        decision_csv,
        report_path,
        canonical_path,
    )
    with decision_csv.open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert summary.counts_by_decision["accept_candidate"] == 0
    assert row["raw"] == "表面摩擦"
    assert row["original_raw"] == "表面摩擦音"
    assert row["decision_recommendation"] == "needs_review"
    assert "surface_too_descriptive" in row["decision_reason"]


def test_v2_pipeline_plans_cleaner_batch0_rows(tmp_path: Path) -> None:
    _, surface_csv, _, canonical_path, _ = _run_cleanup(
        tmp_path,
        [
            _intake_row("摩擦声", "Friction"),
            _intake_row("擦蹭声", "Friction"),
            _intake_row("磨蹭声", "Friction"),
            _intake_row("表面摩擦音", "Friction"),
            _intake_row("铁链", "Chain", slot="object"),
            _intake_row("锁链", "Chain", slot="object"),
        ],
    )
    decision_csv = tmp_path / "decisions_v2.csv"
    decision_report = tmp_path / "decision_v2_report.md"
    recommend_ai_alias_candidate_decisions(
        surface_csv,
        decision_csv,
        decision_report,
        canonical_path,
    )
    plan_csv = tmp_path / "promote_plan_batch0_v2.csv"
    plan_report = tmp_path / "plan_v2_report.md"
    plan_summary = plan_ai_alias_promotions(
        decision_csv,
        plan_csv,
        plan_report,
        canonical_path,
    )
    planned_rows = _read_surface_rows(plan_csv)
    assert plan_summary.planned_count == 4
    assert [(row["raw"], row["canonical"]) for row in planned_rows] == [
        ("擦蹭", "Friction"),
        ("磨蹭", "Friction"),
        ("铁链", "Chain"),
        ("锁链", "Chain"),
    ]
    assert all(row["batch_id"] == BATCH0_V2_ID for row in planned_rows)
    assert all(row["review_status"] == "proposed_keep" for row in planned_rows)
    assert "promote: `no`" in plan_report.read_text(encoding="utf-8")


def test_effective_raw_prefers_cleaned_value_for_replace_rows() -> None:
    row = {
        "raw": "擦蹭声",
        "cleaned_raw": "擦蹭",
        "surface_action": "replace_raw",
    }
    assert effective_raw(row) == "擦蹭"
