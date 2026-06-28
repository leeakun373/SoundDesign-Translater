"""AI alias prompt pack remains local, structured, and review-only by contract."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from fxengine.canonical_db import DEFAULT_CANONICAL_PATH
from tools.build_ai_alias_prompt_pack import (
    AI_INSTRUCTION,
    EXPECTED_COLUMNS,
    REVIEW_CSV_COLUMNS,
    build_alias_prompt_pack,
)
from tools.build_boom_candidate_evidence import EVIDENCE_COLUMNS


def _evidence_row(
    raw: str,
    canonical: str,
    kind: str,
    slot: str,
    score: int,
    *,
    approved_for_ai: str = "yes",
    qa_flags: str = "",
    existing_canonical_status: str = "existing_unknown",
    example_quality: str = "high",
) -> dict[str, object]:
    example = json.dumps(
        {
            "fx_name": canonical,
            "description": f"A {raw} sound",
            "category": "TEST/IMPACT",
            "cat_id": "TESTImpt",
        },
        separators=(",", ":"),
    )
    return {
        "raw": raw,
        "canonical_guess": canonical,
        "kind": kind,
        "slot_guess": slot,
        "record_count": 123,
        "field_hit_count": 200,
        "example_count": 1,
        "score": score,
        "decision": "candidate" if score >= 70 else "review",
        "reason": "test evidence",
        "source_fields": "fx_name=1; description=1; keywords=0; filename=0",
        "example_1": example,
        "example_2": "",
        "example_3": "",
        "catid_samples": "TESTImpt",
        "category_samples": "TEST/IMPACT",
        "source_files": "synthetic.csv",
        "fx_name_hits": 100,
        "description_hits": 10,
        "keywords_hits": 80,
        "filename_hits": 20,
        "field_quality": "high",
        "example_quality": example_quality,
        "category_alignment": "aligned",
        "existing_canonical_status": existing_canonical_status,
        "approved_for_ai": approved_for_ai,
        "qa_flags": qa_flags,
    }


def _write_candidates(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVIDENCE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_review_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _review_row(
    mode: str,
    raw: str,
    canonical: str,
    kind: str,
    slot: str,
    recommendation: str,
) -> dict[str, str]:
    return {
        "mode": mode,
        "raw": raw,
        "canonical": canonical,
        "kind": kind,
        "slot": slot,
        "existing_canonical_status": "existing_unknown",
        "approved_for_ai": "yes",
        "field_quality": "high",
        "example_quality": "high",
        "category_alignment": "aligned",
        "qa_flags": "",
        "review_risk": "medium",
        "recommendation": recommendation,
        "reason": "test review",
        "example_summary": canonical,
    }


def _candidate_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    candidate_dir = tmp_path / "candidates"
    _write_candidates(
        candidate_dir / "action_candidates.csv",
        [
            _evidence_row("hit", "Hit", "token", "action", 75),
            _evidence_row("crack", "Crack", "token", "action", 75),
            _evidence_row(
                "impact",
                "Impact",
                "token",
                "action",
                90,
                existing_canonical_status="existing_keep",
            ),
            _evidence_row(
                "short",
                "Short",
                "token",
                "modifier",
                60,
                approved_for_ai="no",
                qa_flags="detail_modifier",
            ),
        ],
    )
    _write_candidates(
        candidate_dir / "phrase_candidates.csv",
        [_evidence_row("single shot", "Single Shot", "phrase", "action", 75)],
    )
    _write_candidates(
        candidate_dir / "object_candidates.csv",
        [_evidence_row("gun", "Gun", "token", "object", 75)],
    )
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    return (
        candidate_dir / "action_candidates.csv",
        candidate_dir / "phrase_candidates.csv",
        candidate_dir / "object_candidates.csv",
        canonical_path,
        tmp_path,
    )


def test_new_candidate_review_csv_excludes_gun_and_keeps_allow_prompt_only(tmp_path: Path) -> None:
    action_path, phrase_path, object_path, canonical_path, root = _candidate_fixture(tmp_path)
    review_csv = root / "reviewed.csv"
    _write_review_csv(
        review_csv,
        [
            _review_row("new_candidate", "gun", "Gun", "token", "object", "alias_only"),
            _review_row("new_candidate", "hit", "Hit", "token", "action", "allow_prompt"),
            _review_row("new_candidate", "crack", "Crack", "token", "action", "allow_prompt"),
            _review_row(
                "new_candidate",
                "single shot",
                "Single Shot",
                "phrase",
                "action",
                "allow_prompt",
            ),
        ],
    )

    summary = build_alias_prompt_pack(
        action_path,
        phrase_path,
        object_path,
        root / "reviewed_new_candidate",
        root / "reviewed_new_candidate_report.md",
        canonical_path,
        review_csv=review_csv,
        review_recommendation="allow_prompt",
    )
    items = [
        json.loads(line)
        for line in Path(summary.jsonl_path).read_text(encoding="utf-8").splitlines()
    ]

    assert summary.review_csv_path == str(review_csv)
    assert summary.promote is False
    assert summary.ai_invoked is False
    assert {item["canonical"] for item in items} == {"Hit", "Crack", "Single Shot"}
    assert "Gun" not in {item["canonical"] for item in items}
    assert summary.skip_reason_counts.get("review_alias_only") == 1


def test_alias_expansion_review_csv_keeps_alias_only_and_excludes_block(tmp_path: Path) -> None:
    action_path, phrase_path, object_path, canonical_path, root = _candidate_fixture(tmp_path)
    review_csv = root / "reviewed.csv"
    _write_review_csv(
        review_csv,
        [
            _review_row("alias_expansion", "impact", "Impact", "token", "action", "alias_only"),
            _review_row("alias_expansion", "hit", "Hit", "token", "action", "allow_prompt"),
            _review_row("alias_expansion", "gun", "Gun", "token", "object", "alias_only"),
            _review_row("alias_expansion", "crack", "Crack", "token", "action", "block"),
            _review_row(
                "alias_expansion",
                "single shot",
                "Single Shot",
                "phrase",
                "action",
                "allow_prompt",
            ),
        ],
    )

    summary = build_alias_prompt_pack(
        action_path,
        phrase_path,
        object_path,
        root / "reviewed_alias_expansion",
        root / "reviewed_alias_expansion_report.md",
        canonical_path,
        mode="alias_expansion",
        review_csv=review_csv,
    )
    items = [
        json.loads(line)
        for line in Path(summary.jsonl_path).read_text(encoding="utf-8").splitlines()
    ]

    assert {item["canonical"] for item in items} == {"Impact", "Hit", "Gun", "Single Shot"}
    assert "Crack" not in {item["canonical"] for item in items}
    assert summary.skip_reason_counts.get("review_block") == 1


def test_review_csv_absent_preserves_legacy_behavior(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "candidates"
    _write_candidates(
        candidate_dir / "action_candidates.csv",
        [_evidence_row("knock", "Knock", "token", "action", 75)],
    )
    _write_candidates(candidate_dir / "phrase_candidates.csv", [])
    _write_candidates(candidate_dir / "object_candidates.csv", [])
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())

    summary = build_alias_prompt_pack(
        candidate_dir / "action_candidates.csv",
        candidate_dir / "phrase_candidates.csv",
        candidate_dir / "object_candidates.csv",
        tmp_path / "prompt_pack",
        tmp_path / "prompt_report.md",
        canonical_path,
    )

    assert summary.review_csv_path is None
    assert summary.item_count == 1
    assert summary.skip_reason_counts == {}


def test_review_csv_does_not_change_canonical_tokens_hash(tmp_path: Path) -> None:
    action_path, phrase_path, object_path, canonical_path, root = _candidate_fixture(tmp_path)
    review_csv = root / "reviewed.csv"
    _write_review_csv(
        review_csv,
        [_review_row("new_candidate", "hit", "Hit", "token", "action", "allow_prompt")],
    )
    before = canonical_path.read_bytes()

    summary = build_alias_prompt_pack(
        action_path,
        phrase_path,
        object_path,
        root / "reviewed_new_candidate",
        root / "reviewed_new_candidate_report.md",
        canonical_path,
        review_csv=review_csv,
    )

    assert canonical_path.read_bytes() == before
    assert summary.canonical_tokens_changed is False
    report = Path(summary.report_path).read_text(encoding="utf-8")
    assert "AI invoked: `no`" in report
    assert "promote: `no`" in report


def test_prompt_pack_writes_jsonl_without_invoking_ai(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "candidates"
    _write_candidates(
        candidate_dir / "action_candidates.csv",
        [_evidence_row("knock", "Knock", "token", "action", 75)],
    )
    _write_candidates(
        candidate_dir / "phrase_candidates.csv",
        [_evidence_row("metal door slam", "Metal Door Slam", "phrase", "action", 90)],
    )
    _write_candidates(
        candidate_dir / "object_candidates.csv",
        [_evidence_row("door", "Door", "token", "object", 70)],
    )
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    canonical_before = canonical_path.read_bytes()

    summary = build_alias_prompt_pack(
        candidate_dir / "action_candidates.csv",
        candidate_dir / "phrase_candidates.csv",
        candidate_dir / "object_candidates.csv",
        tmp_path / "prompt_pack",
        tmp_path / "prompt_report.md",
        canonical_path,
    )

    lines = Path(summary.jsonl_path).read_text(encoding="utf-8").splitlines()
    items = [json.loads(line) for line in lines]
    assert summary.item_count == len(items) == 3
    assert summary.input_candidate_count == 3
    assert summary.approved_for_ai_count == 3
    assert summary.skipped_count == 0
    assert summary.mode == "new_candidate"
    assert summary.ai_invoked is False
    assert canonical_path.read_bytes() == canonical_before
    assert {item["canonical"] for item in items} == {"Knock", "Metal Door Slam", "Door"}
    assert {item["instruction"] for item in items} == {AI_INSTRUCTION}
    assert all(
        set(example) == {"fx_name", "description", "category", "cat_id"}
        for item in items
        for example in item["examples"]
    )


def test_prompt_preview_requires_review_ai_candidate_rows(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "candidates"
    for filename, rows in (
        (
            "action_candidates.csv",
            [_evidence_row("knock", "Knock", "token", "action", 75)],
        ),
        ("phrase_candidates.csv", []),
        ("object_candidates.csv", []),
    ):
        _write_candidates(candidate_dir / filename, rows)
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())

    summary = build_alias_prompt_pack(
        candidate_dir / "action_candidates.csv",
        candidate_dir / "phrase_candidates.csv",
        candidate_dir / "object_candidates.csv",
        tmp_path / "prompt_pack",
        tmp_path / "prompt_report.md",
        canonical_path,
    )
    preview = Path(summary.preview_path).read_text(encoding="utf-8")
    report = Path(summary.report_path).read_text(encoding="utf-8")

    assert ",".join(EXPECTED_COLUMNS) in preview
    assert "`review_status` must be `review`" in preview
    assert "`source` must be `ai_candidate`" in preview
    assert "`priority` must be `0`" in preview
    assert "Never output `keep`" in preview
    assert "mode: `new_candidate`" in report
    assert "AI invoked: `no`" in report
    assert "canonical_tokens.csv changed: `no`" in report


def test_prompt_pack_skips_unapproved_and_detail_rows(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "candidates"
    _write_candidates(
        candidate_dir / "action_candidates.csv",
        [
            _evidence_row("knock", "Knock", "token", "action", 75),
            _evidence_row(
                "hit",
                "Hit",
                "token",
                "action",
                75,
                approved_for_ai="no",
                qa_flags="ambiguous_token;generic_description_hit",
            ),
            _evidence_row(
                "short",
                "Short",
                "token",
                "modifier",
                60,
                approved_for_ai="no",
                qa_flags="ambiguous_token;detail_modifier",
            ),
        ],
    )
    _write_candidates(candidate_dir / "phrase_candidates.csv", [])
    _write_candidates(candidate_dir / "object_candidates.csv", [])
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())

    summary = build_alias_prompt_pack(
        candidate_dir / "action_candidates.csv",
        candidate_dir / "phrase_candidates.csv",
        candidate_dir / "object_candidates.csv",
        tmp_path / "prompt_pack",
        tmp_path / "prompt_report.md",
        canonical_path,
    )
    items = [
        json.loads(line)
        for line in Path(summary.jsonl_path).read_text(encoding="utf-8").splitlines()
    ]

    assert [item["canonical"] for item in items] == ["Knock"]
    assert summary.input_candidate_count == 3
    assert summary.approved_for_ai_count == 1
    assert summary.skipped_count == 2
    assert summary.skip_reason_counts == {
        "detail_modifier": 1,
        "generic_description_hit": 1,
    }
    report = Path(summary.report_path).read_text(encoding="utf-8")
    assert "skipped_count: `2`" in report
    assert "skip_reason_counts:" in report
    assert "generic_description_hit: `1`" in report


def test_new_candidate_mode_skips_existing_keep_but_alias_expansion_allows_it(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "candidates"
    for filename, rows in (
        (
            "action_candidates.csv",
            [
                _evidence_row(
                    "impact",
                    "Impact",
                    "token",
                    "action",
                    90,
                    existing_canonical_status="existing_keep",
                )
            ],
        ),
        ("phrase_candidates.csv", []),
        ("object_candidates.csv", []),
    ):
        _write_candidates(candidate_dir / filename, rows)
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())

    new_candidate = build_alias_prompt_pack(
        candidate_dir / "action_candidates.csv",
        candidate_dir / "phrase_candidates.csv",
        candidate_dir / "object_candidates.csv",
        tmp_path / "new_candidate",
        tmp_path / "new_candidate_report.md",
        canonical_path,
    )
    alias_expansion = build_alias_prompt_pack(
        candidate_dir / "action_candidates.csv",
        candidate_dir / "phrase_candidates.csv",
        candidate_dir / "object_candidates.csv",
        tmp_path / "alias_expansion",
        tmp_path / "alias_expansion_report.md",
        canonical_path,
        mode="alias_expansion",
    )

    assert new_candidate.item_count == 0
    assert new_candidate.skip_reason_counts == {"existing_keep_not_alias_expansion": 1}
    assert alias_expansion.item_count == 1
    assert alias_expansion.existing_keep_count == 1
    assert alias_expansion.mode == "alias_expansion"


def test_existing_conflict_and_low_examples_never_enter_prompt_pack(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "candidates"
    _write_candidates(
        candidate_dir / "action_candidates.csv",
        [
            _evidence_row(
                "whoosh",
                "Whoosh",
                "token",
                "action",
                90,
                existing_canonical_status="existing_conflict",
            ),
            _evidence_row(
                "scrape",
                "Scrape",
                "token",
                "action",
                90,
                example_quality="low",
            ),
        ],
    )
    _write_candidates(candidate_dir / "phrase_candidates.csv", [])
    _write_candidates(candidate_dir / "object_candidates.csv", [])
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())

    summary = build_alias_prompt_pack(
        candidate_dir / "action_candidates.csv",
        candidate_dir / "phrase_candidates.csv",
        candidate_dir / "object_candidates.csv",
        tmp_path / "prompt_pack",
        tmp_path / "prompt_report.md",
        canonical_path,
        mode="alias_expansion",
    )

    assert summary.item_count == 0
    assert summary.existing_conflict_blocked_count == 1
    assert summary.skip_reason_counts == {
        "existing_conflict": 1,
        "low_example_quality": 1,
    }


@pytest.mark.parametrize("mode", ["new_candidate", "alias_expansion"])
@pytest.mark.parametrize("canonical_status", ["", "existing_review", "unexpected"])
def test_prompt_modes_reject_missing_or_unsupported_canonical_status(
    tmp_path: Path, mode: str, canonical_status: str
) -> None:
    candidate_dir = tmp_path / "candidates"
    _write_candidates(
        candidate_dir / "action_candidates.csv",
        [
            _evidence_row(
                "knock",
                "Knock",
                "token",
                "action",
                90,
                existing_canonical_status=canonical_status,
            )
        ],
    )
    _write_candidates(candidate_dir / "phrase_candidates.csv", [])
    _write_candidates(candidate_dir / "object_candidates.csv", [])
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())

    summary = build_alias_prompt_pack(
        candidate_dir / "action_candidates.csv",
        candidate_dir / "phrase_candidates.csv",
        candidate_dir / "object_candidates.csv",
        tmp_path / "prompt_pack",
        tmp_path / "prompt_report.md",
        canonical_path,
        mode=mode,
    )

    assert summary.item_count == 0
    expected_reason = (
        "not_existing_unknown"
        if mode == "new_candidate"
        else "unsupported_existing_canonical_status"
    )
    assert summary.skip_reason_counts == {expected_reason: 1}
