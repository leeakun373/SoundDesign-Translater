"""Real-input alias workbench remains review-only and canonical-safe."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from fxengine.canonical_db import DEFAULT_CANONICAL_PATH
from tools.build_zh_alias_workbench import (
    WORKBENCH_COLUMNS,
    build_zh_alias_workbench,
    load_case_csv,
)


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_load_case_csv_reads_governance_cases() -> None:
    path = Path(__file__).resolve().parent / "zh_fxname_governance_cases_50.csv"
    cases = load_case_csv(path)
    assert len(cases) == 50
    assert cases[0].case_id == "001"
    assert cases[0].input_text == "木门滑开"


def test_build_workbench_outputs_review_rows_and_preserves_canonical(tmp_path: Path) -> None:
    cases_path = tmp_path / "real_cases.csv"
    candidate_path = tmp_path / "existing_ai_candidates.csv"
    canonical_path = tmp_path / "canonical_tokens.csv"
    output_path = tmp_path / "zh_alias_review_workbench.csv"
    batch_report = tmp_path / "batch_report.md"
    gap_report = tmp_path / "gap_report.md"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())

    _write_csv(
        cases_path,
        (
            "id",
            "input",
            "expected_canonical",
            "expected_fxname",
            "expected_source",
            "confidence_band",
            "must_not_contain",
        ),
        [
            {
                "id": "unknown",
                "input": "陌生词",
                "expected_canonical": "Friction",
                "expected_fxname": "Friction",
                "expected_source": "stable_single",
                "confidence_band": "high",
                "must_not_contain": "",
            },
            {
                "id": "existing_raw",
                "input": "摩擦",
                "expected_canonical": "Friction",
                "expected_fxname": "Friction",
                "expected_source": "stable_single",
                "confidence_band": "high",
                "must_not_contain": "",
            },
            {
                "id": "existing_ai",
                "input": "新擦蹭",
                "expected_canonical": "Friction",
                "expected_fxname": "Friction",
                "expected_source": "stable_single",
                "confidence_band": "high",
                "must_not_contain": "",
            },
            {
                "id": "suffix",
                "input": "陌生声",
                "expected_canonical": "Friction",
                "expected_fxname": "Friction",
                "expected_source": "stable_single",
                "confidence_band": "high",
                "must_not_contain": "",
            },
            {
                "id": "canonical_review",
                "input": "划过",
                "expected_canonical": "",
                "expected_fxname": "",
                "expected_source": "ambiguity_rule",
                "confidence_band": "low",
                "must_not_contain": "",
            },
        ],
    )
    _write_csv(
        candidate_path,
        (
            "raw",
            "original_raw",
            "canonical",
            "slot",
            "decision_recommendation",
            "conflict_group",
            "surface_action",
            "cleaned_raw",
        ),
        [
            {
                "raw": "新擦蹭",
                "original_raw": "新擦蹭声",
                "canonical": "Friction",
                "slot": "action",
                "decision_recommendation": "accept_candidate",
                "conflict_group": "",
                "surface_action": "replace_raw",
                "cleaned_raw": "新擦蹭",
            }
        ],
    )

    before = _sha256(canonical_path)
    summary = build_zh_alias_workbench(
        primary_paths=(cases_path,),
        discovery_roots=(),
        discover_extra=False,
        candidate_paths=(candidate_path,),
        canonical_path=canonical_path,
        output_csv=output_path,
        batch_report=batch_report,
        gap_report=gap_report,
    )
    after = _sha256(canonical_path)
    rows = _read_rows(output_path)

    assert output_path.is_file() and batch_report.is_file() and gap_report.is_file()
    assert tuple(rows[0]) == WORKBENCH_COLUMNS
    assert {row["decision"] for row in rows} == {"pending"}
    assert {row["priority"] for row in rows} == {"0"}

    unknown_row = next(row for row in rows if row["case_id"] == "unknown")
    assert unknown_row["unknown_tokens"] == "陌生词"
    assert unknown_row["suggested_raw"] == "陌生词"

    existing_rows = [row for row in rows if row["case_id"] == "existing_raw"]
    assert all(not row["suggested_raw"] for row in existing_rows)

    ai_row = next(
        row
        for row in rows
        if row["case_id"] == "existing_ai" and row["source"] == "existing_ai_candidate"
    )
    assert ai_row["suggested_raw"] == "新擦蹭"
    assert ai_row["next_action"] == "review_existing_candidate"

    suffix_rows = [row for row in rows if row["case_id"] == "suffix"]
    assert all(not row["suggested_raw"].endswith(("声", "音")) for row in suffix_rows)
    assert all(row["decision"] == "pending" for row in suffix_rows)

    review_rows = [row for row in rows if row["case_id"] == "canonical_review"]
    assert all(not row["suggested_raw"] for row in review_rows)
    assert any(row["review_tokens"] == "划过" for row in review_rows)

    assert before == after
    assert summary.canonical_tokens_changed is False
    assert summary.promote is False
    assert summary.ai_invoked is False
    assert "promote: **no**" in batch_report.read_text(encoding="utf-8")
    assert "AI invoked: **no**" in batch_report.read_text(encoding="utf-8")
