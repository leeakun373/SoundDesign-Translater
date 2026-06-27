"""Noise filtering, n-gram evidence, and inert candidate generation coverage."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest

from fxengine.canonical_db import CANONICAL_COLUMNS, DEFAULT_CANONICAL_PATH
from tools.export_boomone_corpus import export_corpus
from tools.mine_boomone_tokens import _partition_tokens, mine_corpus


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "boomone_sample_metadata.csv"
MINING_FILES = {
    "top_tokens.csv",
    "top_phrases.csv",
    "token_examples.csv",
    "phrase_examples.csv",
    "description_examples.csv",
}
NOISE_TOKENS = {
    "002",
    "416",
    "aif",
    "aiff",
    "ab",
    "co100k",
    "dualmono",
    "edit",
    "final",
    "idx03",
    "index02",
    "mkh8040",
    "mono",
    "mp3",
    "ms",
    "premix",
    "192k",
    "24bit",
    "32bit",
    "96k",
    "master",
    "stereo",
    "take",
    "take01",
    "take03",
    "wav",
    "v1",
    "v2",
    "z",
}


def _build_corpus(tmp_path: Path) -> Path:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    shutil.copyfile(FIXTURE, source_dir / FIXTURE.name)
    db_path = tmp_path / "boomone_records.sqlite"
    export_corpus(
        source_dir,
        db_path,
        tmp_path / "by_ucs",
        tmp_path / "coverage.md",
    )
    return db_path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_metadata_guards_do_not_filter_acoustic_actions() -> None:
    tokens, filtered = _partition_tokens(
        "CRACK SNAP SLAM CACK 96k 24bit MS", "filename"
    )

    assert tokens == ["crack", "snap", "slam"]
    assert set(filtered) == {
        ("cack", "uppercase_code"),
        ("96k", "sample_rate"),
        ("24bit", "bit_depth"),
        ("ms", "channel_or_format"),
    }


def test_record_and_phrase_counts_deduplicate_within_one_record(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "dedup_source"
    source_dir.mkdir()
    (source_dir / "dedup.csv").write_text(
        "Filename,FXName,Description,Keywords,Category,SubCategory,CatID,Microphone\n"
        "door_slam_door_slam_take01.wav,Door Slam Door Slam,"
        "Door slam crack crack,door slam crack crack,DOORS,IMPACT,DOORImpt,MKH8040\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "dedup.sqlite"
    export_corpus(source_dir, db_path, tmp_path / "dedup_ucs", tmp_path / "dedup.md")
    output_dir = tmp_path / "dedup_mining"

    mine_corpus(db_path, output_dir)

    token_rows = {
        row["token"]: row for row in _read_csv(output_dir / "top_tokens.csv")
    }
    assert token_rows["door"]["record_count"] == "1"
    assert token_rows["door"]["field_hit_count"] == "4"
    assert token_rows["crack"]["record_count"] == "1"
    assert token_rows["crack"]["field_hit_count"] == "2"
    phrase_rows = {
        row["phrase"]: row for row in _read_csv(output_dir / "top_phrases.csv")
    }
    assert phrase_rows["door slam"]["record_count"] == "1"
    assert phrase_rows["door slam"]["field_hit_count"] == "4"


def test_mining_filters_noise_and_keeps_metadata_examples(tmp_path: Path) -> None:
    db_path = _build_corpus(tmp_path)
    output_dir = tmp_path / "mining"
    quality_report = tmp_path / "quality.md"

    summary = mine_corpus(
        db_path, output_dir, quality_report_path=quality_report
    )

    assert summary.record_count == 12
    assert {path.name for path in output_dir.iterdir()} == MINING_FILES
    assert NOISE_TOKENS <= set(summary.filtered_tokens)
    assert {
        "bit_depth",
        "channel_or_format",
        "file_extension",
        "microphone_model",
        "pure_numeric",
        "sample_rate",
        "single_letter",
        "stop_or_metadata",
        "take_or_index",
        "version_or_render",
    } <= set(summary.filtered_reasons)

    top_tokens = _read_csv(output_dir / "top_tokens.csv")
    token_names = {row["token"] for row in top_tokens}
    assert not (NOISE_TOKENS & token_names)
    assert {
        "crack",
        "door",
        "metal",
        "snap",
        "wood",
        "knock",
        "slam",
        "scrape",
    } <= token_names
    token_rows = {row["token"]: row for row in top_tokens}
    assert token_rows["door"] == {
        "token": "door",
        "record_count": "2",
        "field_hit_count": "8",
        "example_count": "3",
    }
    assert token_rows["knock"]["record_count"] == "1"
    assert token_rows["knock"]["field_hit_count"] == "4"

    top_phrases = _read_csv(output_dir / "top_phrases.csv")
    assert {int(row["n"]) for row in top_phrases} == {2, 3}
    phrase_names = {row["phrase"] for row in top_phrases}
    assert {"door knock", "metal door slam", "gravel scrape"} <= phrase_names
    assert all(
        not (set(row["phrase"].split()) & NOISE_TOKENS) for row in top_phrases
    )
    phrase_rows = {row["phrase"]: row for row in top_phrases}
    assert phrase_rows["door knock"]["record_count"] == "1"
    assert phrase_rows["door knock"]["field_hit_count"] == "4"

    token_examples = _read_csv(output_dir / "token_examples.csv")
    assert "microphone" in token_examples[0]
    assert "field_source" in token_examples[0]
    assert {row["field_source"] for row in token_examples} <= {
        "fx_name",
        "description",
        "keywords",
        "filename",
    }
    assert {row["microphone"].casefold() for row in token_examples} >= {
        "mkh8040",
        "co100k",
        "416",
    }
    assert len(_read_csv(output_dir / "description_examples.csv")) == 12
    report_text = quality_report.read_text(encoding="utf-8")
    assert "input_files:" in report_text
    assert "Field mapping summary" in report_text
    assert "Top tokens" in report_text
    assert "Top phrases" in report_text
    assert "Filtered token summary" in report_text
    assert "Suspected metadata tokens" in report_text
    assert "Suspected action tokens" in report_text
    assert "Suspected object tokens" in report_text
    assert "Candidate generation summary" in report_text
    assert "canonical_tokens_changed: `no`" in report_text


def test_candidate_generation_is_explicit_review_only_and_deterministic(
    tmp_path: Path,
) -> None:
    db_path = _build_corpus(tmp_path)
    output_dir = tmp_path / "mining"
    candidate_path = tmp_path / "canonical_token_candidates.csv"
    canonical_before = DEFAULT_CANONICAL_PATH.read_bytes()

    summary = mine_corpus(
        db_path,
        output_dir,
        candidate_path=candidate_path,
        candidate_min_count=1,
    )
    first_bytes = candidate_path.read_bytes()
    candidates = _read_csv(candidate_path)

    assert summary.candidate_count == len(candidates) > 0
    assert tuple(candidates[0]) == CANONICAL_COLUMNS
    assert {row["review_status"] for row in candidates} == {"review"}
    assert {row["source"] for row in candidates} == {"boom_mined"}
    assert {row["ambiguity"] for row in candidates} <= {"medium", "high"}
    assert {row["priority"] for row in candidates} == {"0"}
    assert {"knock", "door knock", "metal door slam"} <= {
        row["raw"] for row in candidates
    }
    assert not (NOISE_TOKENS & {row["raw"] for row in candidates})
    assert DEFAULT_CANONICAL_PATH.read_bytes() == canonical_before

    mine_corpus(
        db_path,
        output_dir,
        candidate_path=candidate_path,
        candidate_min_count=1,
    )
    assert candidate_path.read_bytes() == first_bytes
    assert DEFAULT_CANONICAL_PATH.read_bytes() == canonical_before

    with pytest.raises(ValueError, match="canonical_token_candidates.csv"):
        mine_corpus(
            db_path,
            output_dir,
            candidate_path=tmp_path / "canonical_tokens.csv",
        )
    assert not (tmp_path / "canonical_tokens.csv").exists()
    assert DEFAULT_CANONICAL_PATH.read_bytes() == canonical_before
