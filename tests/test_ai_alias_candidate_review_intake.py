"""Review intake generation keeps AI aliases outside canonical runtime data."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

from fxengine.canonical_db import CANONICAL_COLUMNS, DEFAULT_CANONICAL_PATH
from tools.build_ai_alias_candidate_review_intake import (
    INTAKE_COLUMNS,
    SPECIAL_REASONS,
    build_ai_alias_candidate_review_intake,
)


def _source_row(
    canonical: str,
    *,
    ambiguity: str = "medium",
    review_status: str = "review",
    source: str = "ai_candidate",
    priority: str = "0",
) -> dict[str, str]:
    return {
        "raw": f"{canonical} 测试别名",
        "canonical": canonical,
        "slot": "object" if canonical in {"Gun", "Chain", "Door"} else "action",
        "lang": "zh",
        "priority": priority,
        "rule_type": "alias",
        "review_status": review_status,
        "ambiguity": ambiguity,
        "tags": "test",
        "source": source,
        "note": "review intake test",
    }


def _write_source(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANONICAL_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _run(tmp_path: Path, rows: list[dict[str, str]]):
    tmp_path.mkdir(parents=True, exist_ok=True)
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "intake.csv"
    report_path = tmp_path / "report.md"
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    _write_source(input_csv, rows)
    summary = build_ai_alias_candidate_review_intake(
        input_csv,
        output_csv,
        report_path,
        canonical_path,
    )
    return summary, output_csv, report_path, canonical_path


def test_batch_safe_assignment_and_risk(tmp_path: Path) -> None:
    rows = [
        _source_row("Impact", ambiguity="medium"),
        _source_row("Friction", ambiguity="low"),
        _source_row("Chain", ambiguity="low"),
        _source_row("Door", ambiguity="medium"),
        _source_row("Drop", ambiguity="high"),
    ]
    summary, output_csv, _, _ = _run(tmp_path, rows)
    _, intake = _read_rows(output_csv)

    assert all(row["review_batch"] == "batch_safe" for row in intake)
    assert {row["canonical"]: row["review_risk"] for row in intake} == {
        "Impact": "medium",
        "Friction": "low",
        "Chain": "low",
        "Door": "medium",
        "Drop": "medium",
    }
    assert summary.counts_by_batch == {
        "batch_safe": 5,
        "batch_caution": 0,
        "batch_weapon": 0,
    }


def test_batch_caution_assignment_and_risk(tmp_path: Path) -> None:
    rows = [
        _source_row("Hit", ambiguity="high"),
        _source_row("Squeak", ambiguity="high"),
        _source_row("Crack", ambiguity="high"),
        _source_row("Ring", ambiguity="medium"),
    ]
    _, output_csv, _, _ = _run(tmp_path, rows)
    _, intake = _read_rows(output_csv)

    assert all(row["review_batch"] == "batch_caution" for row in intake)
    assert {row["canonical"]: row["review_risk"] for row in intake} == {
        "Hit": "high",
        "Squeak": "high",
        "Crack": "high",
        "Ring": "medium",
    }


def test_batch_weapon_assignment_is_always_high_risk(tmp_path: Path) -> None:
    rows = [
        _source_row("Gun", ambiguity="low"),
        _source_row("Shot", ambiguity="medium"),
        _source_row("Single Shot", ambiguity="high"),
    ]
    _, output_csv, _, _ = _run(tmp_path, rows)
    _, intake = _read_rows(output_csv)

    assert all(row["review_batch"] == "batch_weapon" for row in intake)
    assert all(row["review_risk"] == "high" for row in intake)


def test_caution_review_reasons_are_present(tmp_path: Path) -> None:
    canonicals = ["Hit", "Squeak", "Crack", "Ring"]
    _, output_csv, _, _ = _run(tmp_path, [_source_row(value) for value in canonicals])
    _, intake = _read_rows(output_csv)

    assert {row["canonical"]: row["review_reason"] for row in intake} == {
        canonical: SPECIAL_REASONS[canonical] for canonical in canonicals
    }


def test_weapon_review_reasons_are_present(tmp_path: Path) -> None:
    canonicals = ["Gun", "Shot", "Single Shot"]
    _, output_csv, _, _ = _run(tmp_path, [_source_row(value) for value in canonicals])
    _, intake = _read_rows(output_csv)

    assert {row["canonical"]: row["review_reason"] for row in intake} == {
        canonical: SPECIAL_REASONS[canonical] for canonical in canonicals
    }


def test_review_action_is_pending_and_schema_is_exact(tmp_path: Path) -> None:
    rows = [_source_row("Impact"), _source_row("Hit"), _source_row("Gun")]
    summary, output_csv, report_path, _ = _run(tmp_path, rows)
    fieldnames, intake = _read_rows(output_csv)

    assert fieldnames == list(INTAKE_COLUMNS)
    assert all(row["review_action"] == "pending" for row in intake)
    assert summary.all_actions_pending is True
    report = report_path.read_text(encoding="utf-8")
    assert "intake_count: `3`" in report
    assert "all_review_action_pending: `true`" in report
    assert "promote: `no`" in report


def test_no_keep_and_invalid_governance_values_are_rejected(tmp_path: Path) -> None:
    summary, output_csv, _, _ = _run(tmp_path, [_source_row("Impact")])
    _, intake = _read_rows(output_csv)
    assert summary.has_keep is False
    assert all(row["review_status"] == "review" for row in intake)

    for field, value, message in (
        ("review_status", "keep", "review_status must be review"),
        ("source", "ai_reviewed", "source must be ai_candidate"),
        ("priority", "1", "priority must be 0"),
    ):
        row = _source_row("Impact")
        row[field] = value
        with pytest.raises(ValueError, match=message):
            _run(tmp_path / field, [row])


def test_canonical_tokens_hash_is_unchanged(tmp_path: Path) -> None:
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "intake.csv"
    report_path = tmp_path / "report.md"
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    _write_source(input_csv, [_source_row("Impact"), _source_row("Gun")])
    before = hashlib.sha256(canonical_path.read_bytes()).hexdigest().upper()

    summary = build_ai_alias_candidate_review_intake(
        input_csv,
        output_csv,
        report_path,
        canonical_path,
    )

    after = hashlib.sha256(canonical_path.read_bytes()).hexdigest().upper()
    assert before == after
    assert summary.canonical_tokens_sha256_before == before
    assert summary.canonical_tokens_sha256_after == before
    assert summary.canonical_tokens_changed is False
    assert summary.promote is False

    with pytest.raises(ValueError, match="must not overwrite canonical_tokens.csv"):
        build_ai_alias_candidate_review_intake(
            input_csv,
            canonical_path,
            report_path,
            canonical_path,
        )
    assert hashlib.sha256(canonical_path.read_bytes()).hexdigest().upper() == before
