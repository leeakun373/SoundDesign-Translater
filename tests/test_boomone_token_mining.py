"""Noise filtering, n-gram evidence, and inert candidate generation coverage."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest

from fxengine.canonical_db import CANONICAL_COLUMNS, DEFAULT_CANONICAL_PATH
from tools.export_boomone_corpus import export_corpus
from tools.mine_boomone_tokens import mine_corpus


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
    "co100k",
    "idx03",
    "index02",
    "mkh8040",
    "mp3",
    "take",
    "take01",
    "take03",
    "wav",
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


def test_mining_filters_noise_and_keeps_metadata_examples(tmp_path: Path) -> None:
    db_path = _build_corpus(tmp_path)
    output_dir = tmp_path / "mining"

    summary = mine_corpus(db_path, output_dir)

    assert summary.record_count == 12
    assert {path.name for path in output_dir.iterdir()} == MINING_FILES
    assert NOISE_TOKENS <= set(summary.filtered_tokens)
    assert {
        "file_extension",
        "microphone_model",
        "pure_numeric",
        "stop_or_metadata",
        "take_or_index",
    } <= set(summary.filtered_reasons)

    top_tokens = _read_csv(output_dir / "top_tokens.csv")
    token_names = {row["token"] for row in top_tokens}
    assert not (NOISE_TOKENS & token_names)
    assert {"door", "metal", "wood", "knock", "slam", "scrape"} <= token_names

    top_phrases = _read_csv(output_dir / "top_phrases.csv")
    assert {int(row["n"]) for row in top_phrases} == {2, 3}
    phrase_names = {row["phrase"] for row in top_phrases}
    assert {"door knock", "metal door slam", "gravel scrape"} <= phrase_names
    assert all(
        not (set(row["phrase"].split()) & NOISE_TOKENS) for row in top_phrases
    )

    token_examples = _read_csv(output_dir / "token_examples.csv")
    assert "microphone" in token_examples[0]
    assert {row["microphone"].casefold() for row in token_examples} >= {
        "mkh8040",
        "co100k",
        "416",
    }
    assert len(_read_csv(output_dir / "description_examples.csv")) == 12


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
        candidate_min_count=2,
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
        candidate_min_count=2,
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
