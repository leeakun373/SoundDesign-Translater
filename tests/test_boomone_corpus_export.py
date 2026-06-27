"""Smoke coverage for stable BOOM-style CSV corpus export."""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from pathlib import Path

from fxengine.canonical_db import DEFAULT_CANONICAL_PATH
from tools.export_boomone_corpus import RECORD_COLUMNS, export_corpus


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "boomone_sample_metadata.csv"


def _export_fixture(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    shutil.copyfile(FIXTURE, source_dir / FIXTURE.name)
    db_path = tmp_path / "boomone_records.sqlite"
    ucs_dir = tmp_path / "by_ucs"
    report_path = tmp_path / "coverage.md"
    summary = export_corpus(source_dir, db_path, ucs_dir, report_path)
    return summary, db_path, ucs_dir, report_path


def test_fixture_is_synthetic_and_covers_requested_header_aliases() -> None:
    header = FIXTURE.read_text(encoding="utf-8").splitlines()[0].split(",")
    fixture_text = FIXTURE.read_text(encoding="utf-8")

    assert len(fixture_text.splitlines()) - 1 == 12
    assert "Synthetic BOOM Test" in fixture_text
    assert {"Filename", "File Name", "filename"} <= set(header)
    assert {"FXName", "FX Name", "Title"} <= set(header)
    assert {"Description", "Desc"} <= set(header)
    assert {"Category", "SubCategory", "CatID", "Keywords", "Microphone"} <= set(
        header
    )


def test_export_coalesces_aliases_and_is_stable(tmp_path: Path) -> None:
    canonical_before = DEFAULT_CANONICAL_PATH.read_bytes()
    summary, db_path, ucs_dir, report_path = _export_fixture(tmp_path)

    assert summary.source_files == 1
    assert summary.source_sheets == 1
    assert summary.records == 12
    assert summary.skipped_rows == 0
    assert summary.warnings == ()
    populated_fields = set(RECORD_COLUMNS) - {"vendor_category"}
    assert all(summary.field_counts[field] == 12 for field in populated_fields)
    assert summary.field_counts["vendor_category"] == 0
    assert report_path.is_file()

    connection = sqlite3.connect(db_path)
    try:
        schema = connection.execute("PRAGMA table_info(boomone_records)").fetchall()
        first_three = connection.execute(
            "SELECT filename, fx_name, description FROM boomone_records "
            "ORDER BY record_id LIMIT 3"
        ).fetchall()
        metadata = connection.execute(
            "SELECT category, subcategory, cat_id, keywords, microphone, category_full "
            "FROM boomone_records WHERE filename='glass_clink_05.wav'"
        ).fetchone()
        first_pass = connection.execute(
            "SELECT * FROM boomone_records ORDER BY record_id"
        ).fetchall()
    finally:
        connection.close()

    assert [column[1] for column in schema] == ["record_id", *RECORD_COLUMNS]
    assert first_three == [
        ("wood_door_knock_take01.wav", "Wood Door Knock", "Single hollow wood door knock"),
        ("metal_door_slam_002.wav", "Heavy Metal Door Slam", "Hard metal door slam take 002"),
        ("gravel_scrape_take03.aif", "Gravel Scrape Long", "Long gravel scrape recorded take03 aif"),
    ]
    assert metadata == (
        "GLASS",
        "IMPACT",
        "GLASImpt",
        "glass clink wav index05 CO100K",
        "CO100K",
        "GLASS > IMPACT",
    )

    export_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in ucs_dir.glob("*.csv")
    }
    second_summary = export_corpus(
        tmp_path / "source", db_path, ucs_dir, report_path
    )
    connection = sqlite3.connect(db_path)
    try:
        second_pass = connection.execute(
            "SELECT * FROM boomone_records ORDER BY record_id"
        ).fetchall()
    finally:
        connection.close()
    second_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in ucs_dir.glob("*.csv")
    }

    assert second_summary == summary
    assert second_pass == first_pass
    assert second_hashes == export_hashes
    assert DEFAULT_CANONICAL_PATH.read_bytes() == canonical_before
