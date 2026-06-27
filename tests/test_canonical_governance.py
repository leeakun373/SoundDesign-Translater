"""Canonical review gates, legacy compatibility, and candidate promotion tests."""

from __future__ import annotations

import csv
from pathlib import Path

from fxengine.canonical_audit import audit_canonical_csv
from fxengine.canonical_db import CANONICAL_COLUMNS, CanonicalDB
from fxengine.normalizer import FXNameNormalizer
from tools.promote_token_candidates import promote_candidates


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANONICAL_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _row(
    raw: str,
    canonical: str,
    *,
    review_status: str = "keep",
    rule_type: str = "phrase",
    slot: str = "action",
    ambiguity: str = "low",
    source: str = "manual",
) -> dict[str, object]:
    return {
        "raw": raw,
        "canonical": canonical,
        "slot": slot,
        "lang": "zh",
        "priority": 100 if review_status == "keep" else 0,
        "rule_type": rule_type,
        "review_status": review_status,
        "ambiguity": ambiguity,
        "tags": "test",
        "source": source,
        "note": "review context" if ambiguity == "high" else "",
    }


def test_legacy_seven_column_csv_still_loads_with_defaults(tmp_path: Path) -> None:
    path = tmp_path / "legacy.csv"
    path.write_text(
        "raw,canonical,slot,lang,priority,tags,note\n"
        "测,Test,action,zh,80,test,legacy\n",
        encoding="utf-8",
    )

    db = CanonicalDB(canonical_path=path)

    assert db.token_count == 1
    assert db.raw_csv_row_count == 1
    token = db._tokens[0]
    assert token.rule_type == "stable_single"
    assert token.review_status == "keep"
    assert token.ambiguity == "low"
    assert token.source == "manual"


def test_review_rows_are_unknown_but_keep_rows_reach_final_normalize(
    tmp_path: Path,
) -> None:
    path = tmp_path / "canonical.csv"
    _write_rows(
        path,
        [
            _row("测试保留", "Test Keep"),
            _row(
                "测试待审",
                "",
                review_status="review",
                rule_type="ambiguous_phrase",
                ambiguity="high",
            ),
        ],
    )
    normalizer = FXNameNormalizer(canonical_db=CanonicalDB(canonical_path=path))

    kept = normalizer.normalize("测试保留")
    reviewed = normalizer.normalize("测试待审")

    assert kept.output_fxname == "Test Keep"
    assert kept.tokens[0].source == "canonical_csv"
    assert reviewed.output_fxname == ""
    assert reviewed.unknowns == ["测试待审"]
    assert reviewed.tokens[0].source == "unknown_review"
    assert "canonical_review_required" in reviewed.tokens[0].issues
    assert reviewed.debug["nllb_fallback_used"] is False


def test_keep_phrase_precedes_reviewed_single_character(tmp_path: Path) -> None:
    path = tmp_path / "canonical.csv"
    _write_rows(
        path,
        [
            _row(
                "打",
                "",
                review_status="review",
                rule_type="ambiguous_single",
                ambiguity="high",
            ),
            _row("打门", "Door Knock"),
        ],
    )
    db = CanonicalDB(canonical_path=path)

    matches = db.segment_chinese("打门")

    assert [(match.raw, match.canonical) for match in matches] == [
        ("打门", "Door Knock")
    ]


def test_governed_high_risk_main_rows_obey_runtime_policy() -> None:
    normalizer = FXNameNormalizer()

    assert normalizer.normalize("划过").output_fxname == ""
    assert normalizer.normalize("划过").unknowns == ["划过"]
    assert normalizer.normalize("打门").output_fxname == "Door Knock"
    assert normalizer.normalize("打").output_fxname == ""
    assert normalizer.normalize("打").unknowns == ["打"]


def test_audit_reports_conflicts_and_policy_warnings(tmp_path: Path) -> None:
    conflict_path = tmp_path / "conflict.csv"
    _write_rows(
        conflict_path,
        [
            _row("重复", "First"),
            _row("重复", "Second"),
        ],
    )
    conflict_result = audit_canonical_csv(conflict_path)

    assert conflict_result.passed is False
    assert conflict_result.conflict_count == 1
    assert "conflicting_canonical" in conflict_result.issue_counts

    warning_path = tmp_path / "warnings.csv"
    _write_rows(
        warning_path,
        [
            _row("弱", "Weak", rule_type="weak_token"),
            _row("宽", "Broad", rule_type="ambiguous_single"),
        ],
    )
    warning_result = audit_canonical_csv(warning_path)

    assert warning_result.passed is True
    assert warning_result.error_count == 0
    assert warning_result.issue_counts["weak_token_keep"] == 1
    assert warning_result.issue_counts["ambiguous_single_keep"] == 1


def test_candidate_promotion_only_adds_non_conflicting_keep_rows(
    tmp_path: Path,
) -> None:
    canonical_path = tmp_path / "canonical.csv"
    candidate_path = tmp_path / "candidates.csv"
    conflict_path = tmp_path / "conflicts.csv"
    _write_rows(canonical_path, [_row("已有", "Existing")])
    _write_rows(
        candidate_path,
        [
            _row("新增", "New Token", source="ai_candidate"),
            _row(
                "待审",
                "",
                review_status="review",
                rule_type="ambiguous_phrase",
                ambiguity="high",
                source="ai_candidate",
            ),
            _row("已有", "Conflicting Token", source="ai_reviewed"),
        ],
    )

    result = promote_candidates(
        canonical_path, candidate_path, conflict_path
    )

    assert result.promoted_count == 1
    assert result.skipped_non_keep_count == 1
    assert result.conflict_count == 1
    with canonical_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    assert tuple(reader.fieldnames or ()) == CANONICAL_COLUMNS
    assert {row["raw"]: row["canonical"] for row in rows} == {
        "已有": "Existing",
        "新增": "New Token",
    }
    assert rows[1]["source"] == "ai_candidate"
    with conflict_path.open(encoding="utf-8", newline="") as handle:
        conflicts = list(csv.DictReader(handle))
    assert conflicts[0]["issue_codes"] == "existing_keep_conflict"
