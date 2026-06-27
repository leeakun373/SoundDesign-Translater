#!/usr/bin/env python3
"""Unit tests for BOOM style index builder cleaning and weighting."""

from __future__ import annotations

import sys
import gc
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from build_boom_style_index import (  # noqa: E402
    FIELD_WEIGHTS,
    _accumulate_text_stats,
    _extract_clean_tokens,
    _is_clean_phrase,
    _is_noise_token,
    classify_phrase_quality,
    classify_token_quality,
    create_schema,
    rebuild_derived_tables,
    write_reports,
    ImportStats,
)
from glossary.boom_style import BoomStyleIndex  # noqa: E402


def test_noise_tokens_filtered():
    blocked = [
        "alck",
        "ae",
        "st",
        "ds13",
        "co100k",
        "sanken",
        "mono",
        "microphone",
        "ambtrop",
        "anmlaqua",
        "creasrce",
    ]
    for token in blocked:
        assert _is_noise_token(token), f"expected noise: {token}"

    allowed = [
        "door",
        "impact",
        "movement",
        "room",
        "tone",
        "white",
        "noise",
        "debris",
        "scrape",
        "whoosh",
        "metal",
        "wood",
        "glass",
        "water",
        "animal",
    ]
    for token in allowed:
        assert not _is_noise_token(token), f"expected style token: {token}"


def test_technical_phrases_rejected():
    blocked = [
        "high frequency response",
        "mono sanken co100k",
        "sanken co100k high",
        "co100k high frequency",
        "frequency response",
    ]
    for phrase in blocked:
        assert not _is_clean_phrase(phrase), f"expected blocked phrase: {phrase}"


def test_style_phrases_accepted():
    accepted = [
        "room tone",
        "white noise",
        "tree debris",
        "box scrape",
        "door impact",
        "animal movement",
    ]
    for phrase in accepted:
        assert _is_clean_phrase(phrase), f"expected clean phrase: {phrase}"


def test_field_weights_and_exclusions():
    clean_tokens: Counter[str] = Counter()
    clean_filename_tokens: Counter[str] = Counter()
    clean_phrases: Counter[str] = Counter()
    clean_filename_phrases: Counter[str] = Counter()
    raw_tokens: Counter[str] = Counter()
    raw_filename_tokens: Counter[str] = Counter()
    raw_phrases: Counter[str] = Counter()
    raw_filename_phrases: Counter[str] = Counter()

    record = {
        "fx_name": "Room Tone Wind",
        "filename": "AMB_Room_Tone_Wind.wav",
        "description": "Calm room tone with subtle wind",
        "keywords": "room tone wind",
        "category": "AMBIENCE",
        "subcategory": "ROOM",
        "library": "Roomtones Europe",
        "microphone": "Schoeps ORTF mono sanken co100k high frequency response",
    }

    _accumulate_text_stats(
        record,
        clean_tokens,
        clean_filename_tokens,
        clean_phrases,
        clean_filename_phrases,
        raw_tokens,
        raw_filename_tokens,
        raw_phrases,
        raw_filename_phrases,
    )

    assert clean_tokens["room"] == (
        FIELD_WEIGHTS["fx_name"]
        + FIELD_WEIGHTS["filename"]
        + FIELD_WEIGHTS["description"]
        + FIELD_WEIGHTS["keywords"]
        + FIELD_WEIGHTS["subcategory"]
    )
    assert clean_tokens["tone"] >= FIELD_WEIGHTS["fx_name"]
    assert "sanken" not in clean_tokens
    assert "co100k" not in clean_tokens
    assert "mono" not in clean_tokens
    assert "library" not in clean_tokens
    assert _is_clean_phrase("room tone")
    assert "room tone" in clean_phrases
    assert "high frequency response" not in clean_phrases


def test_clean_tokens_from_fx_name():
    tokens = _extract_clean_tokens("Pre Dawn Breeze Birds AMBTrop_CLOUDFOREST")
    assert "pre" in tokens
    assert "breeze" in tokens
    assert "birds" in tokens
    assert "ambtrop" not in tokens


def test_review_token_is_not_filtered():
    quality = classify_token_quality("BRRRT")
    assert quality["decision"] == "review"
    assert "low_vowel_ratio" in quality["reasons"]
    assert not _is_noise_token("BRRRT")


def test_phrase_quality_review_and_filter():
    review = classify_phrase_quality("brrrt impact")
    assert review["decision"] == "review"
    assert "low_vowel_ratio" in review["reasons"]

    filtered = classify_phrase_quality("mono sanken co100k")
    assert filtered["decision"] == "filter"
    assert "phrase_contains_noise" in filtered["reasons"]


def test_review_items_written_to_noise_report():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db_path = tmp_path / "boom.sqlite"
        report_md = tmp_path / "report.md"
        report_csv = tmp_path / "report.csv"
        noise_md = tmp_path / "noise.md"
        coverage_md = tmp_path / "coverage.md"

        conn = sqlite3.connect(db_path)
        try:
            create_schema(conn)
            run_id = conn.execute(
                """
                INSERT INTO import_runs (
                    started_at, root_path, inventory_path, offset_files, limit_files,
                    rebuild, selected_files
                ) VALUES ('now', '.', 'inventory.csv', 0, 1, 1, 1)
                """
            ).lastrowid
            file_id = conn.execute(
                """
                INSERT INTO source_files (
                    run_id, file_path, file_name, status, sheet_count,
                    fx_record_count, skipped_row_count, warnings
                ) VALUES (?, 'fixture.xlsx', 'fixture.xlsx', 'ok', 1, 1, 0, '[]')
                """,
                (run_id,),
            ).lastrowid
            conn.execute(
                """
                INSERT INTO source_sheets (
                    file_id, sheet_name, row_count, status, fx_record_count,
                    skipped_row_count, warnings
                ) VALUES (?, 'Sheet1', 2, 'ok', 1, 0, '[]')
                """,
                (file_id,),
            )
            conn.execute(
                """
                INSERT INTO fx_records (
                    source_file, sheet_name, row_number, filename, fx_name,
                    description, category, subcategory, cat_id, keywords,
                    library, microphone, raw_json
                ) VALUES (
                    'fixture.xlsx', 'Sheet1', 2, 'BRRRT_Impact.wav', 'BRRRT Impact',
                    '', '', '', '', '', '', '', '{}'
                )
                """
            )
            rebuild_derived_tables(conn)
            conn.commit()
        finally:
            conn.close()

        write_reports(
            stats=ImportStats(selected_files=1, imported_files=1, imported_sheets=1, imported_fx_records=1),
            db_path=db_path,
            report_md=report_md,
            report_csv=report_csv,
            noise_review_md=noise_md,
            field_coverage_md=coverage_md,
            selected_files=["fixture.xlsx"],
        )

        assert "brrrt" in noise_md.read_text(encoding="utf-8")
        assert report_csv.is_file()
        assert coverage_md.is_file()


def test_schema_compatible_with_boom_style_reader():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "boom.sqlite"
        conn = sqlite3.connect(db_path)
        try:
            create_schema(conn)
            conn.execute(
                """
                INSERT INTO fx_records (
                    source_file, sheet_name, row_number, filename, fx_name,
                    description, category, subcategory, cat_id, keywords,
                    library, microphone, raw_json
                ) VALUES (
                    'fixture.xlsx', 'Sheet1', 2, 'Door_Impact.wav', 'Door Impact',
                    '', '', '', '', '', '', '', '{}'
                )
                """
            )
            rebuild_derived_tables(conn)
            assert conn.execute(
                "SELECT 1 FROM tokens WHERE token = 'door'"
            ).fetchone()
            assert conn.execute(
                "SELECT 1 FROM phrases WHERE phrase = 'door impact'"
            ).fetchone()
            assert conn.execute(
                "SELECT 1 FROM token_field_stats WHERE token = 'door'"
            ).fetchone()
            conn.commit()
        finally:
            conn.close()

        styled = BoomStyleIndex(db_path).style_fx_name("Impact Door")
        assert styled.boom_index_used
        del styled
        gc.collect()
