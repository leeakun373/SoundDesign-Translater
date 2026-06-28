"""Candidate evidence scoring, rejection, and write-safety coverage."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

import pytest

from fxengine.canonical_db import CANONICAL_COLUMNS, DEFAULT_CANONICAL_PATH
from tools.build_boom_candidate_evidence import (
    EVIDENCE_COLUMNS,
    _select_examples,
    build_candidate_evidence,
)


QA_COLUMNS = {
    "fx_name_hits",
    "description_hits",
    "keywords_hits",
    "filename_hits",
    "field_quality",
    "example_quality",
    "category_alignment",
    "existing_canonical_status",
    "approved_for_ai",
    "qa_flags",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _make_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    mining_dir = tmp_path / "mining"
    tokens = [
        ("knock", 120, 240),
        ("door", 120, 240),
        ("metal", 120, 240),
        ("short", 120, 240),
        ("cal", 1200, 1200),
    ]
    phrases = [
        ("metal door slam", 120, 240),
        ("sanken high frequency", 1000, 1000),
        ("world war", 1000, 1000),
        ("wwii weapons", 1000, 1000),
        ("away cannon", 1000, 1000),
        ("single shot", 875, 1750),
    ]
    _write_csv(
        mining_dir / "top_tokens.csv",
        ("token", "record_count", "field_hit_count", "example_count"),
        [
            {
                "token": raw,
                "record_count": records,
                "field_hit_count": hits,
                "example_count": 1,
            }
            for raw, records, hits in tokens
        ],
    )
    _write_csv(
        mining_dir / "top_phrases.csv",
        ("phrase", "record_count", "field_hit_count", "example_count", "n"),
        [
            {
                "phrase": raw,
                "record_count": records,
                "field_hit_count": hits,
                "example_count": 1,
                "n": len(raw.split()),
            }
            for raw, records, hits in phrases
        ],
    )

    example_fields = (
        "item",
        "example_rank",
        "field_source",
        "field_value",
        "record_id",
        "library",
        "filename",
        "fx_name",
        "description",
        "cat_id",
        "category",
        "subcategory",
        "microphone",
        "source_file",
    )

    def example_row(raw: str, index: int) -> dict[str, object]:
        return {
            "item": raw,
            "example_rank": 1,
            "field_source": "fx_name",
            "field_value": raw,
            "record_id": index,
            "library": "Synthetic",
            "filename": f"{raw.replace(' ', '_')}.wav",
            "fx_name": raw.title(),
            "description": f"Evidence for {raw}",
            "cat_id": "TESTItem",
            "category": "TEST",
            "subcategory": raw.split()[-1].upper(),
            "microphone": "",
            "source_file": "synthetic.csv",
        }

    token_example_rows = [example_row(raw, index) for index, (raw, *_rest) in enumerate(tokens, 1)]
    phrase_example_rows = [example_row(raw, index) for index, (raw, *_rest) in enumerate(phrases, 100)]
    _write_csv(
        mining_dir / "token_examples.csv",
        ("token", *example_fields[1:]),
        [{"token": row.pop("item"), **row} for row in token_example_rows],
    )
    _write_csv(
        mining_dir / "phrase_examples.csv",
        ("phrase", *example_fields[1:]),
        [{"phrase": row.pop("item"), **row} for row in phrase_example_rows],
    )

    db_path = tmp_path / "boomone.sqlite"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE boomone_records (
                record_id INTEGER PRIMARY KEY,
                library TEXT, filename TEXT, fx_name TEXT, description TEXT,
                cat_id TEXT, category TEXT, subcategory TEXT,
                category_full TEXT, vendor_category TEXT, keywords TEXT,
                microphone TEXT, source_file TEXT
            )
            """
        )
        corpus_values = [raw for raw, *_rest in tokens + phrases]
        for index, raw in enumerate(corpus_values, 1):
            connection.execute(
                """
                INSERT INTO boomone_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    index,
                    "Synthetic",
                    f"{raw.replace(' ', '_')}.wav",
                    raw.title(),
                    raw,
                    "TESTItem",
                    "DOORS" if "door" in raw else "TEST",
                    raw.split()[-1].upper(),
                    "",
                    "",
                    raw,
                    "",
                    "synthetic.csv",
                ),
            )
        connection.commit()
    finally:
        connection.close()

    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    return mining_dir, db_path, canonical_path


def _build(tmp_path: Path, *, write_candidates: bool = False):
    mining_dir, db_path, canonical_path = _make_inputs(tmp_path)
    output_dir = tmp_path / "candidates"
    report_path = tmp_path / "report.md"
    candidate_path = (
        tmp_path / "canonical_token_candidates.csv" if write_candidates else None
    )
    canonical_before = canonical_path.read_bytes()
    summary = build_candidate_evidence(
        mining_dir / "top_tokens.csv",
        mining_dir / "top_phrases.csv",
        mining_dir / "token_examples.csv",
        mining_dir / "phrase_examples.csv",
        db_path,
        canonical_path,
        output_dir,
        report_path,
        write_candidates=candidate_path,
    )
    assert canonical_path.read_bytes() == canonical_before
    return summary, output_dir, report_path, candidate_path


def test_known_vocabulary_and_phrase_are_routed_to_review_files(tmp_path: Path) -> None:
    summary, output_dir, _report, _candidate_path = _build(tmp_path)

    evidence = {row["raw"]: row for row in _read_csv(output_dir / "candidate_evidence.csv")}
    assert tuple(evidence["knock"]) == EVIDENCE_COLUMNS
    assert QA_COLUMNS <= set(evidence["knock"])
    assert evidence["knock"]["slot_guess"] == "action"
    assert evidence["knock"]["decision"] == "candidate"
    assert evidence["door"]["slot_guess"] == "object"
    assert evidence["metal"]["slot_guess"] == "material"
    assert evidence["short"]["slot_guess"] == "modifier"
    assert evidence["short"]["decision"] == "review"
    assert evidence["short"]["approved_for_ai"] == "no"
    assert "detail_modifier" in evidence["short"]["qa_flags"]

    phrase = evidence["metal door slam"]
    assert phrase["slot_guess"] == "action"
    assert int(phrase["score"]) >= 70
    assert phrase["decision"] == "candidate"
    assert "metal door slam" in {
        row["raw"] for row in _read_csv(output_dir / "phrase_candidates.csv")
    }
    assert summary.canonical_tokens_changed is False
    assert summary.total_evidence_count == len(evidence)
    assert summary.approved_for_ai_count + summary.blocked_for_ai_count == len(evidence)
    assert Path(summary.qa_report_path).is_file()


@pytest.mark.parametrize(
    "raw",
    [
        "cal",
        "sanken high frequency",
        "world war",
        "wwii weapons",
        "away cannon",
    ],
)
def test_metadata_and_library_noise_is_rejected(tmp_path: Path, raw: str) -> None:
    _summary, output_dir, _report, _candidate_path = _build(tmp_path)
    rejected = {row["raw"]: row for row in _read_csv(output_dir / "rejected_noise.csv")}

    assert rejected[raw]["decision"] == "reject"


def test_single_shot_is_review_not_candidate(tmp_path: Path) -> None:
    _summary, output_dir, _report, _candidate_path = _build(tmp_path)
    phrases = {row["raw"]: row for row in _read_csv(output_dir / "phrase_candidates.csv")}

    assert phrases["single shot"]["decision"] == "review"


def test_optional_candidate_write_is_review_only_and_hash_guarded(tmp_path: Path) -> None:
    summary, _output_dir, report_path, candidate_path = _build(
        tmp_path, write_candidates=True
    )
    assert candidate_path is not None
    candidates = _read_csv(candidate_path)

    assert summary.written_candidate_count == len(candidates) > 0
    assert tuple(candidates[0]) == CANONICAL_COLUMNS
    assert {row["review_status"] for row in candidates} == {"review"}
    assert {row["source"] for row in candidates} == {"boom_mined"}
    assert {row["priority"] for row in candidates} == {"0"}
    assert "canonical_tokens.csv changed: `no`" in report_path.read_text(
        encoding="utf-8"
    )


def test_candidate_write_refuses_canonical_filename(tmp_path: Path) -> None:
    mining_dir, db_path, canonical_path = _make_inputs(tmp_path)

    with pytest.raises(ValueError, match="canonical_token_candidates.csv"):
        build_candidate_evidence(
            mining_dir / "top_tokens.csv",
            mining_dir / "top_phrases.csv",
            mining_dir / "token_examples.csv",
            mining_dir / "phrase_examples.csv",
            db_path,
            canonical_path,
            tmp_path / "output",
            tmp_path / "report.md",
            write_candidates=tmp_path / "canonical_tokens.csv",
        )


def _build_context_case(
    tmp_path: Path,
    raw: str,
    kind: str,
    records: list[dict[str, str]],
    example_sources: list[str],
) -> dict[str, str]:
    mining_dir = tmp_path / "mining"
    frequency = {
        "record_count": len(records),
        "field_hit_count": sum(
            raw in str(record.get(field, "")).casefold()
            for record in records
            for field in ("fx_name", "description", "keywords", "filename")
        ),
        "example_count": len(example_sources),
    }
    if kind == "token":
        _write_csv(
            mining_dir / "top_tokens.csv",
            ("token", "record_count", "field_hit_count", "example_count"),
            [{"token": raw, **frequency}],
        )
        _write_csv(
            mining_dir / "top_phrases.csv",
            ("phrase", "record_count", "field_hit_count", "example_count", "n"),
            [],
        )
    else:
        _write_csv(
            mining_dir / "top_tokens.csv",
            ("token", "record_count", "field_hit_count", "example_count"),
            [],
        )
        _write_csv(
            mining_dir / "top_phrases.csv",
            ("phrase", "record_count", "field_hit_count", "example_count", "n"),
            [{"phrase": raw, **frequency, "n": len(raw.split())}],
        )

    example_fields = (
        "example_rank",
        "field_source",
        "field_value",
        "record_id",
        "library",
        "filename",
        "fx_name",
        "description",
        "cat_id",
        "category",
        "subcategory",
        "microphone",
        "source_file",
    )
    example_rows = []
    for index, source in enumerate(example_sources, 1):
        record = records[min(index - 1, len(records) - 1)]
        example_rows.append(
            {
                "example_rank": index,
                "field_source": source,
                "field_value": record.get(source, ""),
                "record_id": index,
                "library": "Synthetic",
                "filename": record.get("filename", ""),
                "fx_name": record.get("fx_name", ""),
                "description": record.get("description", ""),
                "cat_id": record.get("cat_id", ""),
                "category": record.get("category", ""),
                "subcategory": record.get("subcategory", ""),
                "microphone": record.get("microphone", ""),
                "source_file": record.get("source_file", f"source-{index}.csv"),
            }
        )
    _write_csv(
        mining_dir / "token_examples.csv",
        ("token", *example_fields),
        ([{"token": raw, **row} for row in example_rows] if kind == "token" else []),
    )
    _write_csv(
        mining_dir / "phrase_examples.csv",
        ("phrase", *example_fields),
        ([{"phrase": raw, **row} for row in example_rows] if kind == "phrase" else []),
    )

    db_path = tmp_path / "context.sqlite"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE boomone_records (
                record_id INTEGER PRIMARY KEY, library TEXT, filename TEXT,
                fx_name TEXT, description TEXT, cat_id TEXT, category TEXT,
                subcategory TEXT, category_full TEXT, vendor_category TEXT,
                keywords TEXT, microphone TEXT, source_file TEXT
            )
            """
        )
        for index, record in enumerate(records, 1):
            connection.execute(
                "INSERT INTO boomone_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    index,
                    "Synthetic",
                    record.get("filename", "clean.wav"),
                    record.get("fx_name", ""),
                    record.get("description", ""),
                    record.get("cat_id", ""),
                    record.get("category", ""),
                    record.get("subcategory", ""),
                    "",
                    "",
                    record.get("keywords", ""),
                    record.get("microphone", ""),
                    record.get("source_file", f"source-{index}.csv"),
                ),
            )
        connection.commit()
    finally:
        connection.close()

    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    output_dir = tmp_path / "candidates"
    build_candidate_evidence(
        mining_dir / "top_tokens.csv",
        mining_dir / "top_phrases.csv",
        mining_dir / "token_examples.csv",
        mining_dir / "phrase_examples.csv",
        db_path,
        canonical_path,
        output_dir,
        tmp_path / "evidence_report.md",
    )
    return _read_csv(output_dir / "candidate_evidence.csv")[0]


def test_duplicate_examples_are_deduplicated_and_fx_name_wins() -> None:
    shared = {
        "fx_name": "Metal Door Knock",
        "description": "Metal door knock",
        "category": "DOORS",
        "subcategory": "KNOCK",
        "cat_id": "DOORKnck",
        "source_file": "same.csv",
    }
    selected, duplicate_count = _select_examples(
        [
            {**shared, "field_source": "description", "example_rank": "1"},
            {**shared, "field_source": "fx_name", "example_rank": "2"},
            {**shared, "field_source": "keywords", "example_rank": "3"},
        ]
    )

    assert len(selected) == 1
    assert selected[0]["field_source"] == "fx_name"
    assert duplicate_count == 2


def test_description_only_hit_is_not_approved_for_ai(tmp_path: Path) -> None:
    records = [
        {
            "fx_name": f"Forest Rain {index}",
            "description": "Rain drops hit broad leaves in the forest",
            "category": "AMBIENCE",
            "subcategory": "FOREST",
            "cat_id": "AMBForst",
            "source_file": f"ambience-{index}.csv",
        }
        for index in range(3)
    ]
    row = _build_context_case(tmp_path, "hit", "token", records, ["description"] * 3)

    assert row["field_quality"] == "low"
    assert row["approved_for_ai"] == "no"
    assert "description_only" in row["qa_flags"]
    assert "generic_description_hit" in row["qa_flags"]


def test_tool_gun_is_blocked_but_guns_category_can_be_approved(tmp_path: Path) -> None:
    tool_records = [
        {
            "fx_name": f"Tape Gun Pull {index}",
            "keywords": "tape gun tool",
            "category": "TOOLS",
            "subcategory": "HAND TOOL",
            "cat_id": "TOOLHand",
            "source_file": f"tools-{index}.csv",
        }
        for index in range(3)
    ]
    tool_row = _build_context_case(
        tmp_path / "tool", "gun", "token", tool_records, ["fx_name"] * 3
    )
    weapon_records = [
        {
            "fx_name": f"Rifle Gun Mechanism {index}",
            "keywords": "rifle gun weapon",
            "category": "GUNS",
            "subcategory": "RIFLE",
            "cat_id": "GUNRif",
            "source_file": f"guns-{index}.csv",
        }
        for index in range(3)
    ]
    weapon_row = _build_context_case(
        tmp_path / "weapon", "gun", "token", weapon_records, ["fx_name"] * 3
    )

    assert tool_row["approved_for_ai"] == "no"
    assert "tool_gun_context" in tool_row["qa_flags"]
    assert weapon_row["field_quality"] == "high"
    assert weapon_row["category_alignment"] == "aligned"
    assert weapon_row["approved_for_ai"] == "yes"


def test_shotgun_microphone_blocks_gun_shot_phrase(tmp_path: Path) -> None:
    records = [
        {
            "fx_name": f"Gun Shot Exterior {index}",
            "description": "Captured with a shotgun microphone on location",
            "keywords": "gun shot rifle",
            "category": "GUNS",
            "subcategory": "RIFLE",
            "cat_id": "GUNRif",
            "source_file": f"guns-{index}.csv",
        }
        for index in range(3)
    ]
    row = _build_context_case(
        tmp_path, "gun shot", "phrase", records, ["fx_name"] * 3
    )

    assert row["field_quality"] == "high"
    assert row["approved_for_ai"] == "no"
    assert "shotgun_microphone" in row["qa_flags"]
