"""Machine review for AI prompt candidates stays local and deterministic."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from fxengine.canonical_db import DEFAULT_CANONICAL_PATH
from tools.build_boom_candidate_evidence import EVIDENCE_COLUMNS
from tools.review_ai_prompt_candidates import review_ai_prompt_candidates


def _example(
    fx_name: str,
    *,
    description: str = "",
    category: str = "",
    cat_id: str = "",
) -> str:
    return json.dumps(
        {
            "fx_name": fx_name,
            "description": description,
            "category": category,
            "cat_id": cat_id,
        },
        separators=(",", ":"),
    )


def _evidence_row(
    raw: str,
    canonical: str,
    kind: str,
    slot: str,
    *,
    approved_for_ai: str = "yes",
    qa_flags: str = "",
    existing_canonical_status: str = "existing_unknown",
    example_quality: str = "high",
    category_alignment: str = "aligned",
    field_quality: str = "high",
    example_1: str = "",
    example_2: str = "",
    example_3: str = "",
    fx_name_hits: int = 20,
    description_hits: int = 0,
) -> dict[str, object]:
    return {
        "raw": raw,
        "canonical_guess": canonical,
        "kind": kind,
        "slot_guess": slot,
        "record_count": 100,
        "field_hit_count": 100,
        "example_count": 3,
        "score": 70,
        "decision": "candidate",
        "reason": "test evidence",
        "source_fields": "fx_name=20; description=0; keywords=0; filename=0",
        "example_1": example_1,
        "example_2": example_2,
        "example_3": example_3,
        "catid_samples": "",
        "category_samples": "",
        "source_files": "synthetic.csv",
        "fx_name_hits": fx_name_hits,
        "description_hits": description_hits,
        "keywords_hits": 0,
        "filename_hits": 0,
        "field_quality": field_quality,
        "example_quality": example_quality,
        "category_alignment": category_alignment,
        "existing_canonical_status": existing_canonical_status,
        "approved_for_ai": approved_for_ai,
        "qa_flags": qa_flags,
    }


def _write_evidence(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVIDENCE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_prompt_pack(
    root: Path,
    mode: str,
    items: list[dict[str, object]],
) -> None:
    mode_dir = root / mode
    mode_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = mode_dir / "alias_prompt_items.jsonl"
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def _review_rows(tmp_path: Path, evidence_rows: list[dict[str, object]], items_by_mode: dict[str, list[dict[str, object]]]) -> list[dict[str, str]]:
    evidence_path = tmp_path / "candidate_evidence.csv"
    prompt_root = tmp_path / "prompt_pack"
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    _write_evidence(evidence_path, evidence_rows)
    for mode, items in items_by_mode.items():
        _write_prompt_pack(prompt_root, mode, items)
    (tmp_path / "expanded_examples.csv").write_text(
        "raw,canonical_guess,example_rank,match_field,match_quality,fx_name,description,keywords,filename,cat_id,category,subcategory,source_file,flags\n",
        encoding="utf-8",
    )
    summary = review_ai_prompt_candidates(
        evidence_path,
        tmp_path / "expanded_examples.csv",
        prompt_root,
        tmp_path / "reviewed.csv",
        tmp_path / "review.md",
        canonical_path,
    )
    assert summary.ai_invoked is False
    assert summary.promote is False
    assert summary.canonical_tokens_changed is False
    with (tmp_path / "reviewed.csv").open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _prompt_item(
    canonical: str,
    *,
    kind: str = "token",
    slot: str = "action",
    examples: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "canonical": canonical,
        "slot": slot,
        "candidate_type": kind,
        "record_count": 100,
        "examples": examples or [],
        "instruction": "test",
    }


def test_gun_cannon_long_gun_not_allow_prompt_for_new_candidate(tmp_path: Path) -> None:
    examples = [
        {
            "fx_name": "Long Gun 150m",
            "description": "Antique artillery, historic cannon long gun, cal 38mm.",
            "category": "GUNS/CANNON",
            "cat_id": "GUNCano",
        }
    ]
    rows = _review_rows(
        tmp_path,
        [
            _evidence_row(
                "gun",
                "Gun",
                "token",
                "object",
                qa_flags="ambiguous_token",
                example_1=_example("Long Gun 150m", category="GUNS/CANNON", cat_id="GUNCano"),
            )
        ],
        {
            "new_candidate": [_prompt_item("Gun", kind="token", slot="object", examples=examples)],
            "alias_expansion": [],
        },
    )
    row = rows[0]
    assert row["recommendation"] in {"alias_only", "block"}
    assert row["recommendation"] != "allow_prompt"
    assert "cannon_long_gun_context" in row["reason"]


def test_tape_gun_is_blocked(tmp_path: Path) -> None:
    examples = [
        {
            "fx_name": "Tape Gun Pull",
            "description": "Tape gun adhesive dispenser pull and release.",
            "category": "TOOLS/MISC",
            "cat_id": "",
        }
    ]
    rows = _review_rows(
        tmp_path,
        [
            _evidence_row(
                "gun",
                "Gun",
                "token",
                "object",
                example_1=_example("Tape Gun Pull", description="Tape gun adhesive dispenser pull."),
            )
        ],
        {"new_candidate": [_prompt_item("Gun", kind="token", slot="object", examples=examples)], "alias_expansion": []},
    )
    assert rows[0]["recommendation"] == "block"
    assert "tool_gun_context" in rows[0]["reason"]


def test_hit_description_only_is_blocked(tmp_path: Path) -> None:
    examples = [
        {
            "fx_name": "",
            "description": "The car hit the wall during the chase scene.",
            "category": "VEHICLES/MISC",
            "cat_id": "",
        }
    ]
    rows = _review_rows(
        tmp_path,
        [
            _evidence_row(
                "hit",
                "Hit",
                "token",
                "action",
                qa_flags="generic_description_hit",
                approved_for_ai="no",
                fx_name_hits=0,
                description_hits=20,
                example_1=_example("", description="The car hit the wall during the chase scene."),
            )
        ],
        {"new_candidate": [_prompt_item("Hit", examples=examples)], "alias_expansion": []},
    )
    assert rows[0]["recommendation"] == "block"
    assert "generic_description_hit" in rows[0]["reason"]


def test_hit_fight_impact_allow_prompt_with_high_ambiguity(tmp_path: Path) -> None:
    examples = [
        {
            "fx_name": "Basic Hit Old School",
            "description": "Traditional punch sound with a vintage feel.",
            "category": "FIGHT/IMPACT",
            "cat_id": "FGHTImpt",
        },
        {
            "fx_name": "Button Box Case Hit",
            "description": "Impact of a metal object striking a button box case.",
            "category": "METAL/IMPACT",
            "cat_id": "METLImpt",
        },
    ]
    rows = _review_rows(
        tmp_path,
        [
            _evidence_row(
                "hit",
                "Hit",
                "token",
                "action",
                qa_flags="ambiguous_token",
                example_1=_example(**examples[0]),
                example_2=_example(**examples[1]),
            )
        ],
        {"new_candidate": [_prompt_item("Hit", examples=examples)], "alias_expansion": []},
    )
    row = rows[0]
    assert row["recommendation"] == "allow_prompt"
    assert row["review_risk"] == "high"
    assert "ambiguous_with_impact" in row["reason"]
    assert "forbid_visual_alias_命中" in row["reason"]


def test_squeak_category_mixed_marks_risk(tmp_path: Path) -> None:
    examples = [
        {
            "fx_name": "Dog Toy Chew Teething Ball Squeak Sequence",
            "description": "Squeaking sequences of a dog chew ball.",
            "category": "CARTOON/SQUEAK",
            "cat_id": "TOONSqk",
        },
        {
            "fx_name": "Metal Squeak Constant Fast",
            "description": "Continuous movement with squeaking and ringing.",
            "category": "GUNS/CANNON",
            "cat_id": "METLFric",
        },
    ]
    rows = _review_rows(
        tmp_path,
        [
            _evidence_row(
                "squeak",
                "Squeak",
                "token",
                "action",
                category_alignment="mixed",
                qa_flags="category_mixed",
                example_1=_example(**examples[0]),
                example_2=_example(**examples[1]),
            )
        ],
        {"new_candidate": [_prompt_item("Squeak", examples=examples)], "alias_expansion": []},
    )
    row = rows[0]
    assert row["recommendation"] == "allow_prompt"
    assert row["review_risk"] in {"medium", "high"}
    assert "guns_category_with_metal_squeak_fxname" in row["reason"]


def test_existing_conflict_is_blocked(tmp_path: Path) -> None:
    rows = _review_rows(
        tmp_path,
        [
            _evidence_row(
                "short",
                "Short",
                "token",
                "modifier",
                existing_canonical_status="existing_conflict",
                qa_flags="existing_conflict",
                approved_for_ai="no",
            )
        ],
        {"new_candidate": [_prompt_item("Short", slot="modifier")], "alias_expansion": []},
    )
    assert rows[0]["recommendation"] == "block"
    assert "existing_conflict" in rows[0]["reason"]


def test_existing_keep_is_alias_only(tmp_path: Path) -> None:
    rows = _review_rows(
        tmp_path,
        [
            _evidence_row(
                "impact",
                "Impact",
                "token",
                "action",
                existing_canonical_status="existing_keep",
            )
        ],
        {"alias_expansion": [_prompt_item("Impact", slot="action")], "new_candidate": []},
    )
    assert rows[0]["recommendation"] == "alias_only"
    assert "existing_keep" in rows[0]["reason"]


def test_single_shot_phrase_allow_prompt(tmp_path: Path) -> None:
    examples = [
        {
            "fx_name": "AK47 V1 Single Shot 01 2m",
            "description": "Assault Rifle single shot close mics.",
            "category": "GUNS/RIFLE",
            "cat_id": "GUNRif",
        }
    ]
    rows = _review_rows(
        tmp_path,
        [
            _evidence_row(
                "single shot",
                "Single Shot",
                "phrase",
                "action",
                qa_flags="ambiguous_token",
                example_1=_example(**examples[0]),
            )
        ],
        {
            "new_candidate": [
                _prompt_item("Single Shot", kind="phrase", slot="action", examples=examples)
            ],
            "alias_expansion": [],
        },
    )
    row = rows[0]
    assert row["recommendation"] == "allow_prompt"
    assert row["kind"] == "phrase"
    assert "phrase_candidate" in row["reason"]
    assert "keep_phrase_do_not_split" in row["reason"]


def test_canonical_tokens_hash_unchanged(tmp_path: Path) -> None:
    evidence_path = tmp_path / "candidate_evidence.csv"
    prompt_root = tmp_path / "prompt_pack"
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    before = hashlib.sha256(canonical_path.read_bytes()).hexdigest().upper()
    _write_evidence(
        evidence_path,
        [_evidence_row("hit", "Hit", "token", "action", example_1=_example("Basic Hit Old School", category="FIGHT/IMPACT"))],
    )
    _write_prompt_pack(
        prompt_root,
        "new_candidate",
        [_prompt_item("Hit", examples=[{"fx_name": "Basic Hit Old School", "description": "", "category": "FIGHT/IMPACT", "cat_id": ""}])],
    )
    _write_prompt_pack(prompt_root, "alias_expansion", [])
    (tmp_path / "expanded_examples.csv").write_text(
        "raw,canonical_guess,example_rank,match_field,match_quality,fx_name,description,keywords,filename,cat_id,category,subcategory,source_file,flags\n",
        encoding="utf-8",
    )
    summary = review_ai_prompt_candidates(
        evidence_path,
        tmp_path / "expanded_examples.csv",
        prompt_root,
        tmp_path / "reviewed.csv",
        tmp_path / "review.md",
        canonical_path,
    )
    after = hashlib.sha256(canonical_path.read_bytes()).hexdigest().upper()
    assert before == after
    assert summary.canonical_tokens_sha256 == before
    assert summary.canonical_tokens_changed is False


def test_production_review_outputs_expected_paths() -> None:
    summary = review_ai_prompt_candidates()
    csv_path = Path(summary.csv_path)
    report_path = Path(summary.report_path)
    assert csv_path.is_file()
    assert report_path.is_file()
    assert summary.total_approved >= 5
    assert summary.reviewed_count == 17
