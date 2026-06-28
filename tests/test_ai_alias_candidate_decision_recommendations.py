"""Decision recommendations remain review artifacts and never promote aliases."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

from fxengine.canonical_db import DEFAULT_CANONICAL_PATH
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
        "note": "decision recommendation test",
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


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _run(tmp_path: Path, rows: list[dict[str, str]]):
    tmp_path.mkdir(parents=True, exist_ok=True)
    input_csv = tmp_path / "intake.csv"
    output_csv = tmp_path / "decisions.csv"
    report_path = tmp_path / "report.md"
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


def test_raw_multi_canonical_conflict_forces_needs_review(tmp_path: Path) -> None:
    summary, output_csv, report_path, _, _ = _run(
        tmp_path,
        [
            _intake_row("碰击声", "Hit", risk="high"),
            _intake_row("碰击声", "Impact", risk="medium"),
        ],
    )
    _, rows = _read_rows(output_csv)

    assert all(row["decision_recommendation"] == "needs_review" for row in rows)
    assert {row["conflict_group"] for row in rows} == {"raw_conflict_001"}
    assert all("raw_multi_canonical_conflict" in row["decision_reason"] for row in rows)
    assert summary.conflict_group_count == 1
    assert summary.conflict_candidate_count == 2
    assert "碰击声 / Hit" in report_path.read_text(encoding="utf-8")


def test_object_slot_sound_suffix_forces_needs_review(tmp_path: Path) -> None:
    _, output_csv, _, _, _ = _run(
        tmp_path,
        [_intake_row("金属链响", "Chain", slot="object", risk="low")],
    )
    row = _read_rows(output_csv)[1][0]
    assert row["decision_recommendation"] == "needs_review"
    assert "object_slot_sound_event" in row["decision_reason"]


def test_chain_sound_event_needs_review(tmp_path: Path) -> None:
    _, output_csv, _, _, _ = _run(
        tmp_path,
        [_intake_row("链条声", "Chain", risk="low")],
    )
    row = _read_rows(output_csv)[1][0]
    assert row["decision_recommendation"] == "needs_review"
    assert "object_slot_sound_event" in row["decision_reason"]


def test_door_open_sound_needs_review(tmp_path: Path) -> None:
    _, output_csv, _, _, _ = _run(
        tmp_path,
        [_intake_row("开门声", "Door", risk="medium")],
    )
    row = _read_rows(output_csv)[1][0]
    assert row["decision_recommendation"] == "needs_review"
    assert "object_slot_sound_event" in row["decision_reason"]


def test_gun_broad_weapon_term_needs_review(tmp_path: Path) -> None:
    _, output_csv, _, _, _ = _run(tmp_path, [_intake_row("枪炮", "Gun")])
    row = _read_rows(output_csv)[1][0]
    assert row["decision_recommendation"] == "needs_review"
    assert "broad_weapon_term" in row["decision_reason"]


def test_shot_broad_action_needs_review(tmp_path: Path) -> None:
    _, output_csv, _, _, _ = _run(tmp_path, [_intake_row("发射声", "Shot")])
    row = _read_rows(output_csv)[1][0]
    assert row["decision_recommendation"] == "needs_review"
    assert "too_broad_weapon_action" in row["decision_reason"]


@pytest.mark.parametrize("raw", ["余响", "回响声", "金属回荡"])
def test_ring_tail_or_reverb_needs_review(tmp_path: Path, raw: str) -> None:
    _, output_csv, _, _, _ = _run(tmp_path, [_intake_row(raw, "Ring")])
    row = _read_rows(output_csv)[1][0]
    assert row["decision_recommendation"] == "needs_review"
    assert "tonal_tail_or_reverb_possible" in row["decision_reason"]


def test_safe_low_risk_entity_alias_can_be_accepted(tmp_path: Path) -> None:
    summary, output_csv, _, _, _ = _run(
        tmp_path,
        [_intake_row("铁链", "Chain", risk="low")],
    )
    fieldnames, rows = _read_rows(output_csv)
    row = rows[0]
    assert fieldnames == list(DECISION_COLUMNS)
    assert row["decision_recommendation"] == "accept_candidate"
    assert row["conflict_group"] == ""
    assert summary.counts_by_decision == {
        "accept_candidate": 1,
        "needs_review": 0,
        "reject_candidate": 0,
    }


def test_hit_literal_match_is_rejected_and_fight_alias_is_flagged(tmp_path: Path) -> None:
    _, output_csv, _, _, _ = _run(
        tmp_path,
        [
            _intake_row("命中", "Hit", risk="high"),
            _intake_row("拳击声", "Hit", risk="high"),
        ],
    )
    _, rows = _read_rows(output_csv)
    by_raw = {row["raw"]: row for row in rows}
    assert by_raw["命中"]["decision_recommendation"] == "reject_candidate"
    assert "forbidden_hit_literal_match" in by_raw["命中"]["decision_reason"]
    assert by_raw["拳击声"]["decision_recommendation"] == "needs_review"
    assert "fight_specific" in by_raw["拳击声"]["decision_reason"]


def test_crack_and_squeak_intake_reasons_are_retained(tmp_path: Path) -> None:
    _, output_csv, _, _, _ = _run(
        tmp_path,
        [
            _intake_row("脆裂声", "Crack", review_reason="broad_material_spread"),
            _intake_row("吱吱声", "Squeak", review_reason="category_pollution_possible"),
        ],
    )
    _, rows = _read_rows(output_csv)
    by_canonical = {row["canonical"]: row for row in rows}
    assert "broad_material_spread" in by_canonical["Crack"]["decision_reason"]
    assert "category_pollution_possible" in by_canonical["Squeak"]["decision_reason"]
    assert all(row["decision_recommendation"] == "needs_review" for row in rows)


def test_no_keep_and_keep_input_is_rejected(tmp_path: Path) -> None:
    summary, output_csv, _, _, _ = _run(tmp_path, [_intake_row("铁链", "Chain")])
    _, rows = _read_rows(output_csv)
    assert summary.has_keep is False
    assert all(row["review_status"] == "review" for row in rows)

    with pytest.raises(ValueError, match="review_status must be review"):
        _run(
            tmp_path / "keep",
            [_intake_row("铁链", "Chain", review_status="keep")],
        )


def test_canonical_tokens_hash_is_unchanged(tmp_path: Path) -> None:
    summary, _, report_path, canonical_path, input_csv = _run(
        tmp_path,
        [_intake_row("铁链", "Chain")],
    )
    before = hashlib.sha256(DEFAULT_CANONICAL_PATH.read_bytes()).hexdigest().upper()
    after = hashlib.sha256(canonical_path.read_bytes()).hexdigest().upper()
    assert before == after
    assert summary.canonical_tokens_sha256_before == before
    assert summary.canonical_tokens_sha256_after == before
    assert summary.canonical_tokens_changed is False
    assert summary.promote is False

    with pytest.raises(ValueError, match="must not overwrite canonical_tokens.csv"):
        recommend_ai_alias_candidate_decisions(
            input_csv,
            canonical_path,
            report_path,
            canonical_path,
        )
    assert hashlib.sha256(canonical_path.read_bytes()).hexdigest().upper() == before
