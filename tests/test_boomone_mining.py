"""BOOM metadata corpus and deterministic mining skeleton coverage."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from tools.export_boomone_corpus import export_corpus
from tools.mine_boomone_tokens import mine_corpus


def test_csv_corpus_export_and_mining_outputs(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / "boom.csv"
    source.write_text(
        "Filename,FXName,Description,CatID,Category,SubCategory,Keywords,Microphone\n"
        "door_01.wav,Wood Door Knock,Single wood door knock,DOORKnck,DOORS,KNOCK,wood knock,MKH8040\n"
        "metal_01.wav,Metal Door Slam,Heavy metal door slam,DOOROpen,DOORS,OPEN CLOSE,metal slam,CO100K\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "boomone_records.sqlite"
    ucs_dir = tmp_path / "by_ucs"
    report_path = tmp_path / "coverage.md"

    export_summary = export_corpus(source_dir, db_path, ucs_dir, report_path)

    assert export_summary.records == 2
    assert export_summary.source_files == 1
    assert db_path.is_file()
    assert report_path.is_file()
    assert (ucs_dir / "DOORS.csv").is_file()
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            "SELECT filename, cat_id, category, subcategory, microphone "
            "FROM boomone_records ORDER BY record_id LIMIT 1"
        ).fetchone()
    finally:
        connection.close()
    assert row == ("door_01.wav", "DOORKnck", "DOORS", "KNOCK", "MKH8040")

    mining_dir = tmp_path / "mining"
    mining_summary = mine_corpus(db_path, mining_dir)

    assert mining_summary.record_count == 2
    expected = {
        "top_tokens.csv",
        "top_phrases.csv",
        "token_examples.csv",
        "phrase_examples.csv",
        "description_examples.csv",
    }
    assert {path.name for path in mining_dir.iterdir()} == expected
    with (mining_dir / "top_tokens.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        token_rows = list(csv.DictReader(handle))
    counts = {row["token"]: int(row["count"]) for row in token_rows}
    assert counts["door"] >= 4
    assert counts["knock"] >= 3
