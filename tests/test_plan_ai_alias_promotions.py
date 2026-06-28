"""Batch0 promote planner stays dry-run and never touches canonical_tokens.csv."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

from fxengine.canonical_db import DEFAULT_CANONICAL_PATH
from tools.plan_ai_alias_promotions import (
    BATCH0_ID,
    PLAN_ACTION,
    PLAN_COLUMNS,
    PLANNED_REVIEW_STATUS,
    plan_ai_alias_promotions,
)
from tools.recommend_ai_alias_candidate_decisions import (
    DECISION_COLUMNS,
    INTAKE_COLUMNS,
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
    review_status: str = "review",
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
        "review_status": review_status,
        "ambiguity": review_risk,
        "tags": "test",
        "source": "ai_candidate",
        "note": "plan promotion test",
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


def _run_decisions(tmp_path: Path, rows: list[dict[str, str]]):
    tmp_path.mkdir(parents=True, exist_ok=True)
    input_csv = tmp_path / "intake.csv"
    output_csv = tmp_path / "decisions.csv"
    report_path = tmp_path / "decision_report.md"
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    _write_intake(input_csv, rows)
    summary = recommend_ai_alias_candidate_decisions(
        input_csv,
        output_csv,
        report_path,
        canonical_path,
    )
    return summary, output_csv, report_path, canonical_path, input_csv


def _decision_row(
    raw: str,
    canonical: str,
    *,
    slot: str | None = None,
    batch: str | None = None,
    risk: str | None = None,
    decision: str = "accept_candidate",
    conflict_group: str = "",
    decision_reason: str = "safe_low_risk;standard_alias_review",
) -> dict[str, str]:
    intake = _intake_row(raw, canonical, slot=slot, batch=batch, risk=risk)
    return {
        **intake,
        "decision_recommendation": decision,
        "decision_reason": decision_reason,
        "conflict_group": conflict_group,
    }


def _write_decisions(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DECISION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _read_plan(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _run(tmp_path: Path, rows: list[dict[str, str]]):
    tmp_path.mkdir(parents=True, exist_ok=True)
    input_csv = tmp_path / "decisions.csv"
    output_csv = tmp_path / "promote_plan_batch0.csv"
    report_path = tmp_path / "report.md"
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    _write_decisions(input_csv, rows)
    summary = plan_ai_alias_promotions(
        input_csv,
        output_csv,
        report_path,
        canonical_path,
    )
    return summary, output_csv, report_path, canonical_path, input_csv


def test_only_accept_candidate_batch_safe_without_conflict_is_planned(tmp_path: Path) -> None:
    summary, output_csv, report_path, _, _ = _run(
        tmp_path,
        [
            _decision_row("摩擦声", "Friction"),
            _decision_row("铁链", "Chain", slot="object"),
            _decision_row("冲击声", "Impact", decision="needs_review", decision_reason="safe_medium_risk"),
            _decision_row("枪声", "Shot", batch="batch_weapon", decision="needs_review"),
            _decision_row(
                "碰击声",
                "Impact",
                decision="needs_review",
                conflict_group="raw_conflict_001",
            ),
        ],
    )
    fieldnames, rows = _read_plan(output_csv)
    report = report_path.read_text(encoding="utf-8")

    assert fieldnames == list(PLAN_COLUMNS)
    assert summary.planned_count == 2
    assert summary.skipped_count == 3
    assert summary.skip_reason_counts == {"not_accept_candidate": 3}
    assert {row["raw"] for row in rows} == {"摩擦声", "铁链"}
    assert all(row["decision_recommendation"] == "accept_candidate" for row in rows)
    assert all(row["review_batch"] == "batch_safe" for row in rows)
    assert all(not row["conflict_group"] for row in rows if "conflict_group" in row)
    assert "promote: `no`" in report
    assert "AI invoked: `no`" in report
    assert "canonical_tokens.csv changed: `no`" in report
    assert "This is a dry-run plan only. No runtime row was added." in report


def test_conflict_group_blocks_accept_candidate_from_plan(tmp_path: Path) -> None:
    summary, output_csv, _, _, _ = _run(
        tmp_path,
        [
            _decision_row("摩擦声", "Friction"),
            _decision_row(
                "碰击声",
                "Impact",
                decision="accept_candidate",
                conflict_group="raw_conflict_001",
            ),
        ],
    )
    _, rows = _read_plan(output_csv)
    assert summary.planned_count == 1
    assert summary.skip_reason_counts == {"has_conflict_group": 1}
    assert rows[0]["raw"] == "摩擦声"


def test_plan_rows_use_proposed_keep_not_runtime_keep(tmp_path: Path) -> None:
    _, output_csv, _, _, _ = _run(tmp_path, [_decision_row("锁链", "Chain", slot="object")])
    _, rows = _read_plan(output_csv)
    row = rows[0]
    assert row["review_status"] == PLANNED_REVIEW_STATUS
    assert row["review_status"] != "keep"
    assert row["plan_action"] == PLAN_ACTION
    assert row["batch_id"] == BATCH0_ID
    assert row["rollback_note"] == "no runtime change; delete this plan row"


def test_weapon_canonical_is_skipped_even_if_accept_candidate(tmp_path: Path) -> None:
    summary, output_csv, _, _, _ = _run(
        tmp_path,
        [
            _decision_row(
                "铁链",
                "Chain",
                slot="object",
                decision="accept_candidate",
            ),
            _decision_row(
                "枪械",
                "Gun",
                slot="object",
                batch="batch_weapon",
                decision="accept_candidate",
            ),
        ],
    )
    _, rows = _read_plan(output_csv)
    assert summary.planned_count == 1
    assert summary.skip_reason_counts["weapon_canonical"] == 1
    assert len(rows) == 1
    assert rows[0]["raw"] == "铁链"


def test_current_real_input_plans_six_safe_accept_candidates(tmp_path: Path) -> None:
    input_csv = (
        Path(__file__).resolve().parents[1]
        / "exports"
        / "ai_alias_prompt_pack"
        / "ai_alias_candidates_decision_recommendations.csv"
    )
    if not input_csv.is_file():
        pytest.skip("decision recommendations export not present")

    output_csv = tmp_path / "promote_plan_batch0.csv"
    report_path = tmp_path / "report.md"
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    summary = plan_ai_alias_promotions(
        input_csv,
        output_csv,
        report_path,
        canonical_path,
    )
    _, rows = _read_plan(output_csv)

    assert summary.planned_count == 6
    assert summary.input_count == 48
    assert summary.skipped_count == 42
    planned_pairs = [(row["raw"], row["canonical"]) for row in rows]
    assert planned_pairs == [
        ("摩擦声", "Friction"),
        ("擦蹭声", "Friction"),
        ("磨蹭声", "Friction"),
        ("表面摩擦音", "Friction"),
        ("铁链", "Chain"),
        ("锁链", "Chain"),
    ]


def test_canonical_tokens_hash_is_unchanged(tmp_path: Path) -> None:
    summary, _, report_path, canonical_path, input_csv = _run(
        tmp_path,
        [_decision_row("摩擦声", "Friction")],
    )
    before = hashlib.sha256(DEFAULT_CANONICAL_PATH.read_bytes()).hexdigest().upper()
    after = hashlib.sha256(canonical_path.read_bytes()).hexdigest().upper()
    assert before == after
    assert summary.canonical_tokens_sha256_before == before
    assert summary.canonical_tokens_sha256_after == before
    assert summary.canonical_tokens_changed is False
    assert summary.promote is False
    assert summary.ai_invoked is False

    with pytest.raises(ValueError, match="must not overwrite canonical_tokens.csv"):
        plan_ai_alias_promotions(
            input_csv,
            canonical_path,
            report_path,
            canonical_path,
        )
    assert hashlib.sha256(canonical_path.read_bytes()).hexdigest().upper() == before


def test_keep_input_is_rejected(tmp_path: Path) -> None:
    row = _decision_row("铁链", "Chain", slot="object")
    row["review_status"] = "keep"
    with pytest.raises(ValueError, match="review_status=keep"):
        _run(tmp_path, [row])


def test_end_to_end_from_intake_to_plan(tmp_path: Path) -> None:
    decision_summary, decision_csv, _, canonical_path, _ = _run_decisions(
        tmp_path,
        [
            _intake_row("摩擦声", "Friction", risk="low"),
            _intake_row("冲击声", "Impact", risk="medium"),
            _intake_row("枪声", "Shot"),
        ],
    )
    plan_csv = tmp_path / "promote_plan_batch0.csv"
    report_path = tmp_path / "plan_report.md"
    plan_summary = plan_ai_alias_promotions(
        decision_csv,
        plan_csv,
        report_path,
        canonical_path,
    )
    _, plan_rows = _read_plan(plan_csv)
    assert decision_summary.counts_by_decision["accept_candidate"] == 1
    assert plan_summary.planned_count == 1
    assert plan_rows[0]["raw"] == "摩擦声"
