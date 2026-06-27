#!/usr/bin/env python3
"""Build BOOM FXName style corpus SQLite index from Excel metadata (small-batch import)."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from inventory_boom_excel import (  # noqa: E402
    OOXML_EXTS,
    _extract_headers,
    _iter_ooxml_sheets,
    _pad_row,
    _read_xlsx_rows,
    _read_xlsx_shared_strings,
    _xls_row_values,
)

from glossary.boom_style import DEFAULT_BOOM_INDEX  # noqa: E402

DEFAULT_ROOT = ROOT / "docs" / "训练数据"
DEFAULT_INVENTORY = ROOT / "tests" / "results" / "boom_metadata_inventory.csv"
DEFAULT_REPORT_MD = ROOT / "tests" / "results" / "boom_style_report.md"
DEFAULT_REPORT_CSV = ROOT / "tests" / "results" / "boom_style_import_report.csv"
DEFAULT_NOISE_REVIEW_MD = ROOT / "tests" / "results" / "boom_style_noise_review.md"
DEFAULT_FIELD_COVERAGE_MD = ROOT / "tests" / "results" / "boom_style_field_coverage.md"

INVENTORY_ROLES = (
    "filename-like",
    "fxname-like",
    "description-like",
    "category-like",
    "subcategory-like",
    "keywords-like",
    "catid-like",
    "library-like",
    "microphone-like",
)

ROLE_TO_FX_FIELD = {
    "filename-like": "filename",
    "fxname-like": "fx_name",
    "description-like": "description",
    "category-like": "category",
    "subcategory-like": "subcategory",
    "keywords-like": "keywords",
    "catid-like": "cat_id",
    "library-like": "library",
    "microphone-like": "microphone",
}

COLUMN_PRIORITY: dict[str, list[str]] = {
    "filename": ["Filename", "TrackTitle", "File Name", "File"],
    "fx_name": ["FXName", "FX Name", "Sound Name", "Name", "Title"],
    "description": ["Description", "BWDescription", "Notes", "Desc"],
    "category": ["Category", "Main Category"],
    "subcategory": ["SubCategory", "Sub Category", "Subcategory"],
    "keywords": ["Keywords", "Keyword", "Tags"],
    "cat_id": ["CatID", "Cat ID", "CategoryID"],
    "library": ["Library", "Pack", "Collection"],
    "microphone": ["Microphone", "Mic", "Mics"],
}

ALL_RECORD_FIELDS = tuple(ROLE_TO_FX_FIELD.values())
STAT_FIELDS = ("fx_name", "filename", "description", "keywords", "category", "subcategory")
PHRASE_FIELDS = STAT_FIELDS
EXCLUDED_STYLE_FIELDS = ("cat_id", "library", "microphone")
HIT_RATE_FIELDS = (
    "filename",
    "fx_name",
    "description",
    "category",
    "subcategory",
    "keywords",
    "cat_id",
    "library",
    "microphone",
)

FIELD_WEIGHTS: dict[str, int] = {
    "fx_name": 3,
    "filename": 2,
    "description": 1,
    "keywords": 1,
    "category": 1,
    "subcategory": 1,
}

STOPWORD_TOKENS = {
    "aif",
    "aiff",
    "and",
    "b00m",
    "boom",
    "boomlibrary",
    "com",
    "flac",
    "from",
    "library",
    "mp3",
    "one",
    "of",
    "or",
    "for",
    "to",
    "in",
    "on",
    "at",
    "by",
    "ref",
    "the",
    "wav",
    "with",
    "www",
}

TECHNICAL_TOKENS = {
    "co100k",
    "sanken",
    "microphone",
    "mic",
    "mics",
    "mono",
    "stereo",
    "frequency",
    "response",
    "schoeps",
    "ortf",
    "ortf3d",
    "designed",
    "source",
    "publisher",
    "manufacturer",
    "artist",
    "hi",
}

LIBRARY_ABBREVIATION_TOKENS = {
    # library / pack abbreviations
    "alck",
    "ae",
    "st",
    "alds",
    "ambswmp",
    "ambtrop",
    "anmlaqua",
    "anmlfarm",
    "anmlwild",
    "anmldog",
    "birdprey",
    "creasrce",
    "dsgnsynth",
    "dsgnmisc",
    "dsgntonl",
    "dsgnimpt",
    "expldsgn",
    "creamisc",
    "ap",
    "ck",
    "ds",
}

NOISE_TOKENS = STOPWORD_TOKENS | TECHNICAL_TOKENS | LIBRARY_ABBREVIATION_TOKENS

EXPLICIT_STYLE_TOKENS = {
    "animal",
    "car",
    "click",
    "debris",
    "door",
    "glass",
    "gun",
    "impact",
    "magic",
    "metal",
    "movement",
    "noise",
    "room",
    "scrape",
    "shot",
    "tone",
    "water",
    "war",
    "white",
    "whoosh",
    "wood",
}

COMMON_SUFFIX_WORDS = {
    "attack",
    "back",
    "black",
    "birds",
    "brick",
    "crack",
    "flick",
    "kick",
    "knock",
    "lock",
    "mock",
    "rock",
    "sick",
    "stack",
    "stick",
    "track",
    "trick",
    "truck",
}

LIBRARY_CODE_PREFIXES = (
    "amb",
    "anm",
    "dsg",
    "cre",
    "expl",
)

DS_CODE_RE = re.compile(r"^ds\d{2,3}$", re.IGNORECASE)
THREE_DS_RE = re.compile(r"^3ds\d{2}$", re.IGNORECASE)
CATEGORY_CODE_RE = re.compile(r"^[a-z]{2,6}\d{1,4}[a-z]?$", re.IGNORECASE)
NUMERIC_CODE_RE = re.compile(r"^[a-z]*\d[\da-z+\-]*$", re.IGNORECASE)
PACK_SUFFIX_CODE_RE = re.compile(r"^[a-z]{2,6}(ck|ds)$", re.IGNORECASE)

# Short library identifiers that cannot be distinguished safely by shape alone.
# They are review items, not hard-filtered noise.
PACK_CODE_TOKENS = frozenset({"cwb", "mui"})

# Common compact CatID fragments embedded in BOOM filenames, e.g. GUNCano,
# METLImpt, OBJCont, MACHAppl. Matching both halves avoids classifying normal
# words such as "gunfire" or "vehicle" as codes.
CODE_PREFIX_SUFFIXES: dict[str, frozenset[str]] = {
    "feet": frozenset({"hmn"}),
    "gun": frozenset({"auto", "cano", "mech", "pis", "rif", "shotg"}),
    "mach": frozenset({"appl"}),
    "metl": frozenset({"fric", "impt", "mvmt", "tonl"}),
    "obj": frozenset({"coin", "cont", "hsehld", "key", "misc", "tape"}),
    "tool": frozenset({"powr"}),
    "veh": frozenset({"mech", "moto", "race"}),
}

TECHNICAL_PHRASES = frozenset(
    {
        "high frequency response",
        "mono sanken co100k",
        "sanken co100k high",
        "co100k high frequency",
        "frequency response",
        "sanken co100k",
        "co100k high",
        "high frequency",
    }
)

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-]*")


@dataclass
class SheetInventoryRow:
    file_path: str
    file_name: str
    sheet_name: str
    headers: list[str]
    guessed: dict[str, list[str]]
    warnings: list[str]


@dataclass
class SheetRows:
    sheet_name: str
    headers: list[str]
    rows: list[list[str]]
    warnings: list[str] = field(default_factory=list)


@dataclass
class ImportStats:
    selected_files: int = 0
    imported_files: int = 0
    imported_sheets: int = 0
    imported_fx_records: int = 0
    skipped_rows: int = 0
    duplicated_source_files: int = 0
    failed_files: int = 0
    failed_sheets: int = 0
    warnings: list[str] = field(default_factory=list)
    field_hits: Counter[str] = field(default_factory=Counter)
    file_rows: list[dict[str, Any]] = field(default_factory=list)
    clean_token_counts: Counter[str] = field(default_factory=Counter)
    clean_filename_token_counts: Counter[str] = field(default_factory=Counter)
    clean_phrase_counts: Counter[str] = field(default_factory=Counter)
    clean_filename_phrase_counts: Counter[str] = field(default_factory=Counter)
    raw_token_counts: Counter[str] = field(default_factory=Counter)
    raw_filename_token_counts: Counter[str] = field(default_factory=Counter)
    raw_phrase_counts: Counter[str] = field(default_factory=Counter)
    raw_filename_phrase_counts: Counter[str] = field(default_factory=Counter)


@dataclass
class CorpusStats:
    clean_token_counts: Counter[str] = field(default_factory=Counter)
    clean_filename_token_counts: Counter[str] = field(default_factory=Counter)
    clean_phrase_counts: Counter[str] = field(default_factory=Counter)
    clean_filename_phrase_counts: Counter[str] = field(default_factory=Counter)
    raw_token_counts: Counter[str] = field(default_factory=Counter)
    raw_filename_token_counts: Counter[str] = field(default_factory=Counter)
    raw_phrase_counts: Counter[str] = field(default_factory=Counter)
    raw_filename_phrase_counts: Counter[str] = field(default_factory=Counter)
    filtered_token_counts: Counter[str] = field(default_factory=Counter)
    filtered_filename_token_counts: Counter[str] = field(default_factory=Counter)
    filtered_token_reasons: dict[str, Counter[str]] = field(default_factory=dict)
    filtered_phrase_counts: Counter[str] = field(default_factory=Counter)
    filtered_filename_phrase_counts: Counter[str] = field(default_factory=Counter)
    filtered_phrase_reasons: dict[str, Counter[str]] = field(default_factory=dict)
    review_token_counts: Counter[str] = field(default_factory=Counter)
    review_filename_token_counts: Counter[str] = field(default_factory=Counter)
    review_token_reasons: dict[str, Counter[str]] = field(default_factory=dict)
    review_phrase_counts: Counter[str] = field(default_factory=Counter)
    review_filename_phrase_counts: Counter[str] = field(default_factory=Counter)
    review_phrase_reasons: dict[str, Counter[str]] = field(default_factory=dict)
    token_field_stats: dict[tuple[str, str], list[int]] = field(default_factory=dict)
    phrase_field_stats: dict[tuple[str, str], list[int]] = field(default_factory=dict)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="metadata root directory")
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY), help="inventory CSV path")
    parser.add_argument("--db", default=str(DEFAULT_BOOM_INDEX), help="sqlite output path")
    parser.add_argument("--limit-files", type=int, default=10, help="max Excel files to import")
    parser.add_argument("--offset-files", type=int, default=0, help="skip first N Excel files")
    parser.add_argument("--rebuild", action="store_true", help="drop and recreate database schema")
    parser.add_argument("--report-md", default=str(DEFAULT_REPORT_MD), help="markdown report path")
    parser.add_argument("--report-csv", default=str(DEFAULT_REPORT_CSV), help="csv import report path")
    parser.add_argument(
        "--noise-review-md",
        default=str(DEFAULT_NOISE_REVIEW_MD),
        help="markdown noise review report path",
    )
    parser.add_argument(
        "--field-coverage-md",
        default=str(DEFAULT_FIELD_COVERAGE_MD),
        help="markdown field coverage report path",
    )
    args = parser.parse_args()

    root = Path(args.root)
    inventory_path = Path(args.inventory)
    db_path = Path(args.db)
    report_md = Path(args.report_md)
    report_csv = Path(args.report_csv)
    noise_review_md = Path(args.noise_review_md)
    field_coverage_md = Path(args.field_coverage_md)

    if not root.is_dir():
        print(f"ERROR: root directory not found: {root}", file=sys.stderr)
        return 1
    if not inventory_path.is_file():
        print(f"ERROR: inventory CSV not found: {inventory_path}", file=sys.stderr)
        return 1

    inventory = load_inventory(inventory_path)
    selected_files = select_files(inventory, args.offset_files, args.limit_files)
    if not selected_files:
        print("ERROR: no files selected from inventory", file=sys.stderr)
        return 1

    stats = import_corpus(
        root=root,
        inventory=inventory,
        selected_files=selected_files,
        db_path=db_path,
        inventory_path=inventory_path,
        offset_files=args.offset_files,
        limit_files=args.limit_files,
        rebuild=args.rebuild,
    )

    write_reports(
        stats=stats,
        db_path=db_path,
        report_md=report_md,
        report_csv=report_csv,
        noise_review_md=noise_review_md,
        field_coverage_md=field_coverage_md,
        selected_files=selected_files,
    )

    print(f"Root: {root}")
    print(f"Selected files: {len(selected_files)}")
    print(f"Imported sheets: {stats.imported_sheets}")
    print(f"FX records: {stats.imported_fx_records}")
    print(f"Skipped rows: {stats.skipped_rows}")
    print(f"Warnings: {len(stats.warnings)}")
    print(f"Duplicate source files skipped: {stats.duplicated_source_files}")
    print(f"Database: {db_path}")
    print(f"Report: {report_md}")
    print(f"Noise review: {noise_review_md}")
    print(f"Field coverage: {field_coverage_md}")
    return 0


def load_inventory(path: Path) -> dict[tuple[str, str], SheetInventoryRow]:
    out: dict[tuple[str, str], SheetInventoryRow] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            guessed = {role: _json_list(row.get(role, "[]")) for role in INVENTORY_ROLES}
            key = (row["file_path"], row["sheet_name"])
            out[key] = SheetInventoryRow(
                file_path=row["file_path"],
                file_name=row["file_name"],
                sheet_name=row["sheet_name"],
                headers=_json_list(row.get("header_list", "[]")),
                guessed=guessed,
                warnings=_json_list(row.get("warnings", "[]")),
            )
    return out


def select_files(
    inventory: dict[tuple[str, str], SheetInventoryRow], offset: int, limit: int
) -> list[str]:
    seen: list[str] = []
    for key in sorted(inventory):
        file_path = key[0]
        if file_path not in seen:
            seen.append(file_path)
    return seen[offset : offset + limit]


def import_corpus(
    *,
    root: Path,
    inventory: dict[tuple[str, str], SheetInventoryRow],
    selected_files: list[str],
    db_path: Path,
    inventory_path: Path,
    offset_files: int,
    limit_files: int,
    rebuild: bool,
) -> ImportStats:
    stats = ImportStats()
    stats.selected_files = len(selected_files)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        if rebuild:
            create_schema(conn)
        else:
            ensure_schema(conn)

        run_id = conn.execute(
            """
            INSERT INTO import_runs (
                started_at, root_path, inventory_path, offset_files, limit_files, rebuild,
                selected_files
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now(),
                root.as_posix(),
                inventory_path.as_posix(),
                offset_files,
                limit_files,
                int(rebuild),
                len(selected_files),
            ),
        ).lastrowid

        clean_token_counts: Counter[str] = Counter()
        clean_filename_token_counts: Counter[str] = Counter()
        clean_phrase_counts: Counter[str] = Counter()
        clean_filename_phrase_counts: Counter[str] = Counter()
        raw_token_counts: Counter[str] = Counter()
        raw_filename_token_counts: Counter[str] = Counter()
        raw_phrase_counts: Counter[str] = Counter()
        raw_filename_phrase_counts: Counter[str] = Counter()

        for rel_file in selected_files:
            file_path = root / rel_file
            file_warnings: list[str] = []
            file_fx_count = 0
            file_skipped = 0
            file_sheet_count = 0

            if not rebuild and _source_file_exists(conn, rel_file):
                warn = f"{rel_file}: skipped duplicate source file already present in database"
                stats.duplicated_source_files += 1
                stats.warnings.append(warn)
                _record_import_warning(conn, run_id, rel_file, None, warn)
                stats.file_rows.append(
                    {
                        "file_path": rel_file,
                        "status": "duplicate_skipped",
                        "sheets": 0,
                        "fx_records": 0,
                        "skipped_rows": 0,
                        "warnings": [warn],
                    }
                )
                continue

            if not file_path.is_file():
                warn = f"{rel_file}: file not found"
                stats.warnings.append(warn)
                file_warnings.append(warn)
                stats.failed_files += 1
                _record_import_warning(conn, run_id, rel_file, None, warn)
                conn.execute(
                    """
                    INSERT INTO source_files (run_id, file_path, file_name, status, warnings)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (run_id, rel_file, Path(rel_file).name, "missing", json.dumps(file_warnings)),
                )
                stats.file_rows.append(
                    {
                        "file_path": rel_file,
                        "status": "missing",
                        "sheets": 0,
                        "fx_records": 0,
                        "skipped_rows": 0,
                        "warnings": file_warnings,
                    }
                )
                continue

            file_id = conn.execute(
                """
                INSERT INTO source_files (run_id, file_path, file_name, status, warnings)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, rel_file, file_path.name, "ok", "[]"),
            ).lastrowid
            stats.imported_files += 1

            sheet_names = [
                sheet_name
                for (fp, sheet_name) in sorted(inventory)
                if fp == rel_file and not sheet_name.startswith("(")
            ]

            try:
                workbook_sheets = read_workbook(file_path)
            except Exception as exc:  # noqa: BLE001
                warn = f"{rel_file}: failed to read workbook: {exc}"
                stats.warnings.append(warn)
                file_warnings.append(warn)
                stats.failed_files += 1
                _record_import_warning(conn, run_id, rel_file, None, warn)
                conn.execute(
                    "UPDATE source_files SET status = ?, warnings = ? WHERE id = ?",
                    ("error", json.dumps(file_warnings), file_id),
                )
                stats.file_rows.append(
                    {
                        "file_path": rel_file,
                        "status": "error",
                        "sheets": 0,
                        "fx_records": 0,
                        "skipped_rows": 0,
                        "warnings": file_warnings,
                    }
                )
                continue

            sheets_by_name = {sheet.sheet_name: sheet for sheet in workbook_sheets}

            for sheet_name in sheet_names:
                inv = inventory.get((rel_file, sheet_name))
                if inv is None:
                    continue

                sheet_data = sheets_by_name.get(sheet_name)
                sheet_warnings = list(inv.warnings)
                if sheet_data is None:
                    warn = f"{rel_file}/{sheet_name}: sheet not found in workbook"
                    stats.warnings.append(warn)
                    sheet_warnings.append(warn)
                    stats.failed_sheets += 1
                    _record_import_warning(conn, run_id, rel_file, sheet_name, warn)
                    conn.execute(
                        """
                        INSERT INTO source_sheets (file_id, sheet_name, row_count, status, warnings)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (file_id, sheet_name, 0, "missing", json.dumps(sheet_warnings)),
                    )
                    continue

                sheet_warnings = _merge_reasons(sheet_warnings, sheet_data.warnings)
                for sheet_warning in sheet_warnings:
                    warning = f"{rel_file}/{sheet_name}: {sheet_warning}"
                    stats.warnings.append(warning)
                    _record_import_warning(conn, run_id, rel_file, sheet_name, warning)
                headers = sheet_data.headers or inv.headers
                mapping = build_column_mapping(inv.guessed, headers)
                data_rows = sheet_data.rows[1:] if sheet_data.rows else []

                sheet_id = conn.execute(
                    """
                    INSERT INTO source_sheets (file_id, sheet_name, row_count, status, warnings)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        file_id,
                        sheet_name,
                        len(sheet_data.rows),
                        "ok",
                        json.dumps(sheet_warnings),
                    ),
                ).lastrowid

                inv_role_by_fx = {v: k for k, v in ROLE_TO_FX_FIELD.items()}
                for fx_field, column_name in mapping.items():
                    conn.execute(
                        """
                        INSERT INTO column_mapping (sheet_id, role, column_name)
                        VALUES (?, ?, ?)
                        """,
                        (sheet_id, inv_role_by_fx.get(fx_field, fx_field), column_name),
                    )

                stats.imported_sheets += 1
                file_sheet_count += 1

                try:
                    sheet_fx, sheet_skipped, sheet_warns = import_sheet_rows(
                        conn=conn,
                        sheet_id=sheet_id,
                        rel_file=rel_file,
                        sheet_name=sheet_name,
                        headers=headers,
                        data_rows=data_rows,
                        mapping=mapping,
                        stats=stats,
                        clean_token_counts=clean_token_counts,
                        clean_filename_token_counts=clean_filename_token_counts,
                        clean_phrase_counts=clean_phrase_counts,
                        clean_filename_phrase_counts=clean_filename_phrase_counts,
                        raw_token_counts=raw_token_counts,
                        raw_filename_token_counts=raw_filename_token_counts,
                        raw_phrase_counts=raw_phrase_counts,
                        raw_filename_phrase_counts=raw_filename_phrase_counts,
                    )
                except Exception as exc:  # noqa: BLE001
                    warn = f"{rel_file}/{sheet_name}: import failed: {exc}"
                    stats.warnings.append(warn)
                    sheet_warnings.append(warn)
                    stats.failed_sheets += 1
                    _record_import_warning(conn, run_id, rel_file, sheet_name, warn)
                    conn.execute(
                        "UPDATE source_sheets SET status = ?, warnings = ? WHERE id = ?",
                        ("error", json.dumps(sheet_warnings), sheet_id),
                    )
                    continue

                stats.warnings.extend(sheet_warns)
                file_fx_count += sheet_fx
                file_skipped += sheet_skipped
                conn.execute(
                    """
                    UPDATE source_sheets
                    SET fx_record_count = ?, skipped_row_count = ?
                    WHERE id = ?
                    """,
                    (sheet_fx, sheet_skipped, sheet_id),
                )

            if file_warnings:
                conn.execute(
                    "UPDATE source_files SET warnings = ? WHERE id = ?",
                    (json.dumps(file_warnings), file_id),
                )
            conn.execute(
                """
                UPDATE source_files
                SET sheet_count = ?, fx_record_count = ?, skipped_row_count = ?
                WHERE id = ?
                """,
                (file_sheet_count, file_fx_count, file_skipped, file_id),
            )

            stats.file_rows.append(
                {
                    "file_path": rel_file,
                    "status": "ok",
                    "sheets": file_sheet_count,
                    "fx_records": file_fx_count,
                    "skipped_rows": file_skipped,
                    "warnings": file_warnings,
                }
            )

        corpus_stats = rebuild_derived_tables(conn)
        conn.execute(
            """
            UPDATE import_runs
            SET finished_at = ?,
                imported_files = ?,
                imported_sheets = ?,
                imported_fx_records = ?,
                skipped_rows = ?,
                warnings_count = ?,
                duplicated_source_files = ?,
                failed_files = ?,
                failed_sheets = ?
            WHERE id = ?
            """,
            (
                _now(),
                stats.imported_files,
                stats.imported_sheets,
                stats.imported_fx_records,
                stats.skipped_rows,
                len(stats.warnings),
                stats.duplicated_source_files,
                stats.failed_files,
                stats.failed_sheets,
                run_id,
            ),
        )

    stats.clean_token_counts = corpus_stats.clean_token_counts
    stats.clean_filename_token_counts = corpus_stats.clean_filename_token_counts
    stats.clean_phrase_counts = corpus_stats.clean_phrase_counts
    stats.clean_filename_phrase_counts = corpus_stats.clean_filename_phrase_counts
    stats.raw_token_counts = corpus_stats.raw_token_counts
    stats.raw_filename_token_counts = corpus_stats.raw_filename_token_counts
    stats.raw_phrase_counts = corpus_stats.raw_phrase_counts
    stats.raw_filename_phrase_counts = corpus_stats.raw_filename_phrase_counts
    return stats


def import_sheet_rows(
    *,
    conn: sqlite3.Connection,
    sheet_id: int,
    rel_file: str,
    sheet_name: str,
    headers: list[str],
    data_rows: list[list[str]],
    mapping: dict[str, str],
    stats: ImportStats,
    clean_token_counts: Counter[str],
    clean_filename_token_counts: Counter[str],
    clean_phrase_counts: Counter[str],
    clean_filename_phrase_counts: Counter[str],
    raw_token_counts: Counter[str],
    raw_filename_token_counts: Counter[str],
    raw_phrase_counts: Counter[str],
    raw_filename_phrase_counts: Counter[str],
) -> tuple[int, int, list[str]]:
    warnings: list[str] = []
    imported = 0
    skipped = 0
    col_index = {header: idx for idx, header in enumerate(headers)}

    for row_number, row in enumerate(data_rows, start=2):
        if not _row_has_content(row):
            skipped += 1
            stats.skipped_rows += 1
            continue

        raw_dict = _row_to_dict(headers, row)
        conn.execute(
            """
            INSERT INTO raw_rows (sheet_id, row_number, raw_json)
            VALUES (?, ?, ?)
            """,
            (sheet_id, row_number, json.dumps(raw_dict, ensure_ascii=False)),
        )

        record = extract_fx_record(rel_file, sheet_name, row_number, raw_dict, mapping, col_index)
        if record is None:
            skipped += 1
            stats.skipped_rows += 1
            continue

        for field_name in HIT_RATE_FIELDS:
            if record.get(field_name):
                stats.field_hits[field_name] += 1

        conn.execute(
            """
            INSERT INTO fx_records (
                source_file, sheet_name, row_number,
                filename, fx_name, description, category, subcategory,
                cat_id, keywords, library, microphone, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["source_file"],
                record["sheet_name"],
                record["row_number"],
                record.get("filename"),
                record.get("fx_name"),
                record.get("description"),
                record.get("category"),
                record.get("subcategory"),
                record.get("cat_id"),
                record.get("keywords"),
                record.get("library"),
                record.get("microphone"),
                json.dumps(raw_dict, ensure_ascii=False),
            ),
        )
        imported += 1
        stats.imported_fx_records += 1
        _accumulate_text_stats(
            record,
            clean_token_counts,
            clean_filename_token_counts,
            clean_phrase_counts,
            clean_filename_phrase_counts,
            raw_token_counts,
            raw_filename_token_counts,
            raw_phrase_counts,
            raw_filename_phrase_counts,
        )

    return imported, skipped, warnings


def extract_fx_record(
    rel_file: str,
    sheet_name: str,
    row_number: int,
    raw_dict: dict[str, str],
    mapping: dict[str, str],
    col_index: dict[str, int],
) -> dict[str, Any] | None:
    record: dict[str, Any] = {
        "source_file": rel_file,
        "sheet_name": sheet_name,
        "row_number": row_number,
    }
    for fx_field in ROLE_TO_FX_FIELD.values():
        column = mapping.get(fx_field)
        value = _cell_value(raw_dict, column, col_index) if column else ""
        if value:
            record[fx_field] = value

    if not any(record.get(field) for field in ROLE_TO_FX_FIELD.values()):
        return None
    return record


def build_column_mapping(guessed: dict[str, list[str]], headers: list[str]) -> dict[str, str]:
    header_set = set(headers)
    mapping: dict[str, str] = {}

    for role, fx_field in ROLE_TO_FX_FIELD.items():
        column = _pick_column(guessed.get(role, []), COLUMN_PRIORITY.get(fx_field, []), header_set)
        if column:
            mapping[fx_field] = column

    if "filename" not in mapping:
        column = _filename_fallback(headers)
        if column:
            mapping["filename"] = column

    if "fx_name" not in mapping:
        column = _pick_column([], COLUMN_PRIORITY["fx_name"], header_set)
        if column:
            mapping["fx_name"] = column

    return mapping


def _pick_column(
    guessed_cols: list[str], priority: list[str], header_set: set[str]
) -> str | None:
    for name in priority:
        if name in guessed_cols:
            return name
    if guessed_cols:
        return guessed_cols[0]
    for name in priority:
        if name in header_set:
            return name
    return None


def _filename_fallback(headers: list[str]) -> str | None:
    if not headers:
        return None
    for name in COLUMN_PRIORITY["filename"]:
        if name in headers:
            return name
    first = headers[0]
    lower = first.lower()
    if ".wav" in lower or ".aif" in lower or ".flac" in lower or ".mp3" in lower:
        return first
    return first


def read_workbook(path: Path) -> list[SheetRows]:
    suffix = path.suffix.lower()
    if suffix in OOXML_EXTS:
        return _read_ooxml_rows(path)
    if suffix == ".xls":
        return _read_xls_rows(path)
    raise ValueError(f"unsupported Excel format: {suffix}")


def _read_ooxml_rows(path: Path) -> list[SheetRows]:
    sheets: list[SheetRows] = []
    with zipfile.ZipFile(path) as zf:
        shared = _read_xlsx_shared_strings(zf)
        for sheet_name, sheet_xml in _iter_ooxml_sheets(zf):
            warnings: list[str] = []
            try:
                rows = [_pad_row(row) for row in _read_xlsx_rows(zf, sheet_xml, shared)]
            except Exception as exc:  # noqa: BLE001
                sheets.append(SheetRows(sheet_name, [], [], [f"failed to read sheet: {exc}"]))
                continue
            if not rows:
                sheets.append(SheetRows(sheet_name, [], [], ["empty sheet"]))
                continue
            headers = _extract_headers(rows, warnings)
            sheets.append(SheetRows(sheet_name, headers, rows, warnings))
    return sheets


def _read_xls_rows(path: Path) -> list[SheetRows]:
    try:
        import xlrd
    except ImportError as exc:
        raise RuntimeError(".xls support unavailable: xlrd not installed") from exc

    sheets: list[SheetRows] = []
    workbook = xlrd.open_workbook(str(path), on_demand=True)
    try:
        for index in range(workbook.nsheets):
            sheet_name = workbook.sheet_names()[index]
            warnings: list[str] = []
            try:
                sheet = workbook.sheet_by_index(index)
                rows = [_xls_row_values(sheet, row_idx) for row_idx in range(sheet.nrows)]
            except Exception as exc:  # noqa: BLE001
                sheets.append(SheetRows(sheet_name, [], [], [f"failed to read sheet: {exc}"]))
                continue
            if not rows:
                sheets.append(SheetRows(sheet_name, [], [], ["empty sheet"]))
                continue
            headers = _extract_headers(rows, warnings)
            sheets.append(SheetRows(sheet_name, headers, rows, warnings))
    finally:
        workbook.release_resources()
    return sheets


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS column_mapping;
        DROP TABLE IF EXISTS raw_rows;
        DROP TABLE IF EXISTS fx_records;
        DROP TABLE IF EXISTS source_sheets;
        DROP TABLE IF EXISTS source_files;
        DROP TABLE IF EXISTS import_runs;
        DROP TABLE IF EXISTS tokens;
        DROP TABLE IF EXISTS phrases;
        DROP TABLE IF EXISTS token_field_stats;
        DROP TABLE IF EXISTS phrase_field_stats;
        DROP TABLE IF EXISTS filtered_tokens;
        DROP TABLE IF EXISTS filtered_phrases;
        DROP TABLE IF EXISTS noise_review_items;
        DROP TABLE IF EXISTS import_warnings;
        """
    )
    ensure_schema(conn)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS import_runs (
            id INTEGER PRIMARY KEY,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            root_path TEXT NOT NULL,
            inventory_path TEXT NOT NULL,
            offset_files INTEGER NOT NULL,
            limit_files INTEGER NOT NULL,
            rebuild INTEGER NOT NULL DEFAULT 0,
            selected_files INTEGER NOT NULL DEFAULT 0,
            imported_files INTEGER NOT NULL DEFAULT 0,
            imported_sheets INTEGER NOT NULL DEFAULT 0,
            imported_fx_records INTEGER NOT NULL DEFAULT 0,
            skipped_rows INTEGER NOT NULL DEFAULT 0,
            warnings_count INTEGER NOT NULL DEFAULT 0,
            duplicated_source_files INTEGER NOT NULL DEFAULT 0,
            failed_files INTEGER NOT NULL DEFAULT 0,
            failed_sheets INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS source_files (
            id INTEGER PRIMARY KEY,
            run_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            status TEXT NOT NULL,
            sheet_count INTEGER NOT NULL DEFAULT 0,
            fx_record_count INTEGER NOT NULL DEFAULT 0,
            skipped_row_count INTEGER NOT NULL DEFAULT 0,
            warnings TEXT,
            FOREIGN KEY (run_id) REFERENCES import_runs(id)
        );
        CREATE TABLE IF NOT EXISTS source_sheets (
            id INTEGER PRIMARY KEY,
            file_id INTEGER NOT NULL,
            sheet_name TEXT NOT NULL,
            row_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            fx_record_count INTEGER NOT NULL DEFAULT 0,
            skipped_row_count INTEGER NOT NULL DEFAULT 0,
            warnings TEXT,
            FOREIGN KEY (file_id) REFERENCES source_files(id)
        );
        CREATE TABLE IF NOT EXISTS column_mapping (
            id INTEGER PRIMARY KEY,
            sheet_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            column_name TEXT NOT NULL,
            FOREIGN KEY (sheet_id) REFERENCES source_sheets(id)
        );
        CREATE TABLE IF NOT EXISTS raw_rows (
            id INTEGER PRIMARY KEY,
            sheet_id INTEGER NOT NULL,
            row_number INTEGER NOT NULL,
            raw_json TEXT NOT NULL,
            FOREIGN KEY (sheet_id) REFERENCES source_sheets(id)
        );
        CREATE TABLE IF NOT EXISTS fx_records (
            id INTEGER PRIMARY KEY,
            source_file TEXT NOT NULL,
            sheet_name TEXT NOT NULL,
            row_number INTEGER NOT NULL,
            filename TEXT,
            fx_name TEXT,
            description TEXT,
            category TEXT,
            subcategory TEXT,
            cat_id TEXT,
            keywords TEXT,
            library TEXT,
            microphone TEXT,
            raw_json TEXT
        );
        CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            freq INTEGER NOT NULL,
            filename_freq INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS phrases (
            phrase TEXT PRIMARY KEY,
            n INTEGER NOT NULL,
            freq INTEGER NOT NULL,
            filename_freq INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS token_field_stats (
            token TEXT NOT NULL,
            field_name TEXT NOT NULL,
            raw_freq INTEGER NOT NULL,
            weighted_freq INTEGER NOT NULL,
            PRIMARY KEY (token, field_name)
        );
        CREATE TABLE IF NOT EXISTS phrase_field_stats (
            phrase TEXT NOT NULL,
            field_name TEXT NOT NULL,
            raw_freq INTEGER NOT NULL,
            weighted_freq INTEGER NOT NULL,
            PRIMARY KEY (phrase, field_name)
        );
        CREATE TABLE IF NOT EXISTS filtered_tokens (
            token TEXT PRIMARY KEY,
            freq INTEGER NOT NULL,
            filename_freq INTEGER NOT NULL DEFAULT 0,
            reasons TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS filtered_phrases (
            phrase TEXT PRIMARY KEY,
            n INTEGER NOT NULL,
            freq INTEGER NOT NULL,
            filename_freq INTEGER NOT NULL DEFAULT 0,
            reasons TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS noise_review_items (
            id INTEGER PRIMARY KEY,
            item_type TEXT NOT NULL,
            item TEXT NOT NULL,
            n INTEGER NOT NULL DEFAULT 1,
            freq INTEGER NOT NULL,
            filename_freq INTEGER NOT NULL DEFAULT 0,
            decision TEXT NOT NULL,
            reasons TEXT NOT NULL,
            details_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS import_warnings (
            id INTEGER PRIMARY KEY,
            run_id INTEGER NOT NULL,
            source_file TEXT,
            sheet_name TEXT,
            warning TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES import_runs(id)
        );
        CREATE INDEX IF NOT EXISTS idx_fx_records_source ON fx_records(source_file, sheet_name);
        CREATE INDEX IF NOT EXISTS idx_phrases_weight ON phrases(freq, filename_freq);
        CREATE INDEX IF NOT EXISTS idx_phrases_n ON phrases(n);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_source_files_unique_file_path
            ON source_files(file_path);
        CREATE INDEX IF NOT EXISTS idx_token_field_stats_field ON token_field_stats(field_name);
        CREATE INDEX IF NOT EXISTS idx_phrase_field_stats_field ON phrase_field_stats(field_name);
        CREATE INDEX IF NOT EXISTS idx_noise_review_items_item ON noise_review_items(item_type, item);
        CREATE INDEX IF NOT EXISTS idx_import_warnings_run ON import_warnings(run_id);
        """
    )
    _ensure_column(conn, "import_runs", "selected_files", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "import_runs", "imported_files", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "import_runs", "imported_sheets", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "import_runs", "imported_fx_records", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "import_runs", "skipped_rows", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "import_runs", "warnings_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "import_runs", "duplicated_source_files", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "import_runs", "failed_files", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "import_runs", "failed_sheets", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "source_files", "sheet_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "source_files", "fx_record_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "source_files", "skipped_row_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "source_sheets", "fx_record_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "source_sheets", "skipped_row_count", "INTEGER NOT NULL DEFAULT 0")


def _ensure_column(
    conn: sqlite3.Connection, table_name: str, column_name: str, definition: str
) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _source_file_exists(conn: sqlite3.Connection, rel_file: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM source_files WHERE file_path = ? LIMIT 1",
        (rel_file,),
    ).fetchone()
    return row is not None


def _record_import_warning(
    conn: sqlite3.Connection,
    run_id: int,
    source_file: str | None,
    sheet_name: str | None,
    warning: str,
) -> None:
    conn.execute(
        """
        INSERT INTO import_warnings (run_id, source_file, sheet_name, warning, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (run_id, source_file, sheet_name, warning, _now()),
    )


def rebuild_derived_tables(conn: sqlite3.Connection) -> CorpusStats:
    stats = CorpusStats()
    for record in _iter_fx_records(conn):
        _accumulate_field_source_stats(record, stats)

    token_distributions = _field_distributions(stats.token_field_stats)
    phrase_distributions = _field_distributions(stats.phrase_field_stats)
    for record in _iter_fx_records(conn):
        _accumulate_quality_stats(record, stats, token_distributions, phrase_distributions)

    write_token_phrase_tables(
        conn,
        stats.clean_token_counts,
        stats.clean_filename_token_counts,
        stats.clean_phrase_counts,
        stats.clean_filename_phrase_counts,
    )
    write_field_stat_tables(conn, stats)
    write_filter_review_tables(conn, stats, token_distributions, phrase_distributions)
    return stats


def _iter_fx_records(conn: sqlite3.Connection) -> Iterable[dict[str, Any]]:
    columns = ("source_file", "sheet_name", "row_number", *ALL_RECORD_FIELDS)
    query = f"SELECT {', '.join(columns)} FROM fx_records"
    for row in conn.execute(query):
        yield dict(zip(columns, row))


def _accumulate_field_source_stats(record: dict[str, Any], stats: CorpusStats) -> None:
    for field_name in ALL_RECORD_FIELDS:
        text = str(record.get(field_name) or "")
        if not text.strip():
            continue
        raw_weight = FIELD_WEIGHTS.get(field_name, 1)
        style_weight = FIELD_WEIGHTS.get(field_name, 0)
        raw_tokens = _extract_raw_tokens(text)
        if not raw_tokens:
            continue

        for token in raw_tokens:
            stats.raw_token_counts[token] += raw_weight
            if field_name == "filename":
                stats.raw_filename_token_counts[token] += raw_weight
            _bump_field_stats(stats.token_field_stats, token, field_name, style_weight)

        for phrase in _extract_phrases(raw_tokens):
            stats.raw_phrase_counts[phrase] += raw_weight
            if field_name == "filename":
                stats.raw_filename_phrase_counts[phrase] += raw_weight
            _bump_field_stats(stats.phrase_field_stats, phrase, field_name, style_weight)


def _accumulate_quality_stats(
    record: dict[str, Any],
    stats: CorpusStats,
    token_distributions: dict[str, dict[str, int]],
    phrase_distributions: dict[str, dict[str, int]],
) -> None:
    for field_name in ALL_RECORD_FIELDS:
        text = str(record.get(field_name) or "")
        if not text.strip():
            continue
        raw_tokens = _extract_raw_tokens(text)
        if not raw_tokens:
            continue

        raw_weight = FIELD_WEIGHTS.get(field_name, 1)
        style_weight = FIELD_WEIGHTS.get(field_name, 0)
        field_excluded = field_name in EXCLUDED_STYLE_FIELDS or field_name not in STAT_FIELDS

        for token in raw_tokens:
            quality = classify_token_quality(token, token_distributions.get(token))
            if field_excluded:
                reasons = _merge_reasons(quality["reasons"], ["field_excluded"])
                _bump_filtered_token(stats, token, raw_weight, field_name, reasons)
                continue

            if quality["decision"] == "filter":
                _bump_filtered_token(stats, token, style_weight, field_name, quality["reasons"])
            elif quality["decision"] == "review":
                _bump_review_token(stats, token, style_weight, field_name, quality["reasons"])
            else:
                stats.clean_token_counts[token] += style_weight
                if field_name == "filename":
                    stats.clean_filename_token_counts[token] += style_weight

        for phrase in _extract_phrases(raw_tokens):
            quality = classify_phrase_quality(phrase, phrase_distributions.get(phrase))
            if field_excluded:
                reasons = _merge_reasons(quality["reasons"], ["field_excluded"])
                _bump_filtered_phrase(stats, phrase, raw_weight, field_name, reasons)
                continue

            if quality["decision"] == "filter":
                _bump_filtered_phrase(stats, phrase, style_weight, field_name, quality["reasons"])
            elif quality["decision"] == "review":
                _bump_review_phrase(stats, phrase, style_weight, field_name, quality["reasons"])
            else:
                stats.clean_phrase_counts[phrase] += style_weight
                if field_name == "filename":
                    stats.clean_filename_phrase_counts[phrase] += style_weight


def _bump_field_stats(
    field_stats: dict[tuple[str, str], list[int]],
    item: str,
    field_name: str,
    weighted_freq: int,
) -> None:
    bucket = field_stats.setdefault((item, field_name), [0, 0])
    bucket[0] += 1
    bucket[1] += weighted_freq


def _field_distributions(
    field_stats: dict[tuple[str, str], list[int]]
) -> dict[str, dict[str, int]]:
    distributions: dict[str, dict[str, int]] = defaultdict(dict)
    for (item, field_name), counts in field_stats.items():
        distributions[item][field_name] = counts[0]
    return dict(distributions)


def _bump_filtered_token(
    stats: CorpusStats, token: str, weight: int, field_name: str, reasons: list[str]
) -> None:
    stats.filtered_token_counts[token] += weight
    if field_name == "filename":
        stats.filtered_filename_token_counts[token] += weight
    _reason_counter(stats.filtered_token_reasons, token).update(reasons)


def _bump_filtered_phrase(
    stats: CorpusStats, phrase: str, weight: int, field_name: str, reasons: list[str]
) -> None:
    stats.filtered_phrase_counts[phrase] += weight
    if field_name == "filename":
        stats.filtered_filename_phrase_counts[phrase] += weight
    _reason_counter(stats.filtered_phrase_reasons, phrase).update(reasons)


def _bump_review_token(
    stats: CorpusStats, token: str, weight: int, field_name: str, reasons: list[str]
) -> None:
    stats.review_token_counts[token] += weight
    if field_name == "filename":
        stats.review_filename_token_counts[token] += weight
    _reason_counter(stats.review_token_reasons, token).update(reasons)


def _bump_review_phrase(
    stats: CorpusStats, phrase: str, weight: int, field_name: str, reasons: list[str]
) -> None:
    stats.review_phrase_counts[phrase] += weight
    if field_name == "filename":
        stats.review_filename_phrase_counts[phrase] += weight
    _reason_counter(stats.review_phrase_reasons, phrase).update(reasons)


def _reason_counter(mapping: dict[str, Counter[str]], item: str) -> Counter[str]:
    counter = mapping.get(item)
    if counter is None:
        counter = Counter()
        mapping[item] = counter
    return counter


def _merge_reasons(*groups: Iterable[str]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in merged:
                merged.append(reason)
    return merged


def write_field_stat_tables(conn: sqlite3.Connection, stats: CorpusStats) -> None:
    conn.execute("DELETE FROM token_field_stats")
    conn.execute("DELETE FROM phrase_field_stats")
    conn.executemany(
        """
        INSERT INTO token_field_stats(token, field_name, raw_freq, weighted_freq)
        VALUES (?, ?, ?, ?)
        """,
        [
            (token, field_name, counts[0], counts[1])
            for (token, field_name), counts in stats.token_field_stats.items()
        ],
    )
    conn.executemany(
        """
        INSERT INTO phrase_field_stats(phrase, field_name, raw_freq, weighted_freq)
        VALUES (?, ?, ?, ?)
        """,
        [
            (phrase, field_name, counts[0], counts[1])
            for (phrase, field_name), counts in stats.phrase_field_stats.items()
        ],
    )


def write_filter_review_tables(
    conn: sqlite3.Connection,
    stats: CorpusStats,
    token_distributions: dict[str, dict[str, int]],
    phrase_distributions: dict[str, dict[str, int]],
) -> None:
    conn.execute("DELETE FROM filtered_tokens")
    conn.execute("DELETE FROM filtered_phrases")
    conn.execute("DELETE FROM noise_review_items")
    conn.executemany(
        """
        INSERT INTO filtered_tokens(token, freq, filename_freq, reasons)
        VALUES (?, ?, ?, ?)
        """,
        [
            (
                token,
                freq,
                stats.filtered_filename_token_counts[token],
                _reasons_json(stats.filtered_token_reasons.get(token, Counter())),
            )
            for token, freq in stats.filtered_token_counts.items()
            if freq > 0
        ],
    )
    conn.executemany(
        """
        INSERT INTO filtered_phrases(phrase, n, freq, filename_freq, reasons)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                phrase,
                len(phrase.split()),
                freq,
                stats.filtered_filename_phrase_counts[phrase],
                _reasons_json(stats.filtered_phrase_reasons.get(phrase, Counter())),
            )
            for phrase, freq in stats.filtered_phrase_counts.items()
            if freq > 0
        ],
    )

    review_rows: list[tuple[str, str, int, int, int, str, str, str]] = []
    for token, freq in stats.review_token_counts.items():
        if freq <= 0:
            continue
        quality = classify_token_quality(token, token_distributions.get(token))
        reasons = stats.review_token_reasons.get(token, Counter())
        review_rows.append(
            (
                "token",
                token,
                1,
                freq,
                stats.review_filename_token_counts[token],
                quality["decision"],
                _reasons_json(reasons),
                json.dumps(quality, ensure_ascii=False, sort_keys=True),
            )
        )
    for phrase, freq in stats.review_phrase_counts.items():
        if freq <= 0:
            continue
        quality = classify_phrase_quality(phrase, phrase_distributions.get(phrase))
        reasons = stats.review_phrase_reasons.get(phrase, Counter())
        review_rows.append(
            (
                "phrase",
                phrase,
                len(phrase.split()),
                freq,
                stats.review_filename_phrase_counts[phrase],
                quality["decision"],
                _reasons_json(reasons),
                json.dumps(quality, ensure_ascii=False, sort_keys=True),
            )
        )
    conn.executemany(
        """
        INSERT INTO noise_review_items(
            item_type, item, n, freq, filename_freq, decision, reasons, details_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        review_rows,
    )


def _reasons_json(reasons: Counter[str]) -> str:
    ranked = [reason for reason, _count in reasons.most_common()]
    return json.dumps(ranked, ensure_ascii=False)


def write_token_phrase_tables(
    conn: sqlite3.Connection,
    token_counts: Counter[str],
    filename_token_counts: Counter[str],
    phrase_counts: Counter[str],
    filename_phrase_counts: Counter[str],
) -> None:
    conn.execute("DELETE FROM tokens")
    conn.execute("DELETE FROM phrases")
    conn.executemany(
        "INSERT INTO tokens(token, freq, filename_freq) VALUES (?, ?, ?)",
        [
            (token, freq, filename_token_counts[token])
            for token, freq in token_counts.items()
        ],
    )
    conn.executemany(
        "INSERT INTO phrases(phrase, n, freq, filename_freq) VALUES (?, ?, ?, ?)",
        [
            (phrase, len(phrase.split()), freq, filename_phrase_counts[phrase])
            for phrase, freq in phrase_counts.items()
        ],
    )


def load_token_phrase_stats(db_path: Path) -> tuple[list[tuple], dict[int, list[tuple]]]:
    with sqlite3.connect(db_path) as conn:
        token_rows = conn.execute(
            "SELECT token, freq, filename_freq FROM tokens ORDER BY freq DESC, token LIMIT 100"
        ).fetchall()
        phrase_rows: dict[int, list[tuple]] = {}
        for n in (2, 3, 4):
            phrase_rows[n] = conn.execute(
                """
                SELECT phrase, freq, filename_freq
                FROM phrases
                WHERE n = ?
                ORDER BY freq DESC, phrase
                LIMIT 100
                """,
                (n,),
            ).fetchall()
    return token_rows, phrase_rows


def _write_legacy_reports(
    *,
    stats: ImportStats,
    db_path: Path,
    report_md: Path,
    report_csv: Path,
    selected_files: list[str],
    clean_token_rows: list[tuple[str, int, int]],
    clean_phrase_rows: list[tuple[str, int, int, int]],
    raw_token_rows: list[tuple[str, int, int]],
    raw_phrase_rows: dict[int, list[tuple]],
    token_rows: list[tuple],
) -> None:
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_csv.parent.mkdir(parents=True, exist_ok=True)

    hit_rates = _field_hit_rates(stats)
    generated = _now()

    md_lines = [
        "# BOOM FXName Style Corpus 0.1C Clean Style Stats Report",
        "",
        f"- 生成时间：{generated}",
        f"- 数据库：`{db_path.as_posix()}`",
        f"- 选中文件数：**{len(selected_files)}**",
        f"- 统计策略：字段加权（fx_name×3, filename×2, 其余×1）；排除 library/microphone；clean 过滤库编号/技术词",
        "",
        "## Summary",
        "",
        "| 指标 | 值 |",
        "| --- | --- |",
        f"| imported files | {stats.imported_files} |",
        f"| imported sheets | {stats.imported_sheets} |",
        f"| imported fx_records | {stats.imported_fx_records} |",
        f"| skipped rows | {stats.skipped_rows} |",
        f"| warnings | {len(stats.warnings)} |",
        "",
        "## Field recognition hit rate",
        "",
        "| field | hit_count | hit_rate |",
        "| --- | --- | --- |",
    ]
    for field_name in HIT_RATE_FIELDS:
        hits = hit_rates.get(field_name, (0, 0.0))
        md_lines.append(f"| {field_name} | {hits[0]} | {hits[1]:.1%} |")

    if stats.warnings:
        md_lines.extend(["", "## Warnings", ""])
        for warning in stats.warnings:
            md_lines.append(f"- {warning}")

    md_lines.extend(
        [
            "",
            "## Top 100 clean style tokens",
            "",
            "| token | freq | filename_freq |",
            "| --- | --- | --- |",
        ]
    )
    for token, freq, filename_freq in clean_token_rows:
        md_lines.append(f"| {token} | {freq} | {filename_freq} |")

    md_lines.extend(
        [
            "",
            "## Top 100 clean style phrases",
            "",
            "| phrase | n | freq | filename_freq |",
            "| --- | --- | --- | --- |",
        ]
    )
    for phrase, n, freq, filename_freq in clean_phrase_rows:
        md_lines.append(f"| {phrase} | {n} | {freq} | {filename_freq} |")

    md_lines.extend(
        [
            "",
            "## Top 100 raw tokens (unfiltered, for comparison)",
            "",
            "| token | freq | filename_freq |",
            "| --- | --- | --- |",
        ]
    )
    for token, freq, filename_freq in raw_token_rows:
        md_lines.append(f"| {token} | {freq} | {filename_freq} |")

    md_lines.extend(
        [
            "",
            "## Top 100 indexed tokens (SQLite, clean weighted)",
            "",
            "| token | freq | filename_freq |",
            "| --- | --- | --- |",
        ]
    )
    for token, freq, filename_freq in token_rows:
        md_lines.append(f"| {token} | {freq} | {filename_freq} |")

    for n in (2, 3, 4):
        md_lines.extend(
            [
                "",
                f"## Top 100 raw {n}-gram phrases (unfiltered, for comparison)",
                "",
                "| phrase | freq | filename_freq |",
                "| --- | --- | --- |",
            ]
        )
        for phrase, freq, filename_freq in raw_phrase_rows.get(n, []):
            md_lines.append(f"| {phrase} | {freq} | {filename_freq} |")

    report_md.write_text("\n".join(md_lines), encoding="utf-8")

    with report_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["file_path", "status", "sheets", "fx_records", "skipped_rows", "warnings"],
        )
        writer.writeheader()
        for row in stats.file_rows:
            writer.writerow(
                {
                    "file_path": row["file_path"],
                    "status": row["status"],
                    "sheets": row["sheets"],
                    "fx_records": row["fx_records"],
                    "skipped_rows": row["skipped_rows"],
                    "warnings": json.dumps(row["warnings"], ensure_ascii=False),
                }
            )


def _field_hit_rates(stats: ImportStats) -> dict[str, tuple[int, float]]:
    total = stats.imported_fx_records or 1
    return {field: (stats.field_hits[field], stats.field_hits[field] / total) for field in HIT_RATE_FIELDS}


def _accumulate_text_stats(
    record: dict[str, Any],
    clean_token_counts: Counter[str],
    clean_filename_token_counts: Counter[str],
    clean_phrase_counts: Counter[str],
    clean_filename_phrase_counts: Counter[str],
    raw_token_counts: Counter[str],
    raw_filename_token_counts: Counter[str],
    raw_phrase_counts: Counter[str],
    raw_filename_phrase_counts: Counter[str],
) -> None:
    for field_name in PHRASE_FIELDS:
        text = str(record.get(field_name) or "")
        if not text.strip():
            continue
        weight = FIELD_WEIGHTS.get(field_name, 1)
        raw_tokens = _extract_raw_tokens(text)
        clean_tokens = _extract_clean_tokens(text)

        if raw_tokens:
            for token in raw_tokens:
                raw_token_counts[token] += weight
                if field_name == "filename":
                    raw_filename_token_counts[token] += weight
            for phrase in _extract_phrases(raw_tokens):
                raw_phrase_counts[phrase] += weight
                if field_name == "filename":
                    raw_filename_phrase_counts[phrase] += weight

        if clean_tokens:
            for token in clean_tokens:
                clean_token_counts[token] += weight
                if field_name == "filename":
                    clean_filename_token_counts[token] += weight
            for phrase in _extract_phrases(clean_tokens):
                if not _is_clean_phrase(phrase):
                    continue
                clean_phrase_counts[phrase] += weight
                if field_name == "filename":
                    clean_filename_phrase_counts[phrase] += weight


def _extract_raw_tokens(text: str) -> list[str]:
    tokens = [_normalize_token(word) for word in WORD_RE.findall(text)]
    return [token for token in tokens if token and not _is_basic_noise_token(token)]


def _extract_clean_tokens(text: str) -> list[str]:
    return [token for token in _extract_raw_tokens(text) if _is_style_token(token)]


def _extract_phrases(tokens: list[str]) -> Iterable[str]:
    for n in range(2, 5):
        for i in range(0, len(tokens) - n + 1):
            yield " ".join(tokens[i : i + n])


def _is_clean_phrase(phrase: str) -> bool:
    return classify_phrase_quality(phrase)["decision"] == "keep"


def _is_style_token(token: str) -> bool:
    return classify_token_quality(token)["decision"] == "keep"


def _is_basic_noise_token(token: str) -> bool:
    if len(token) <= 1:
        return True
    if token.isdigit():
        return True
    return False


def _is_noise_token(token: str) -> bool:
    return classify_token_quality(token)["decision"] == "filter"


def classify_token_quality(
    token: str, field_distribution: dict[str, int] | None = None
) -> dict[str, Any]:
    original = token.strip()
    normalized = _normalize_token(original)
    distribution = dict(field_distribution or {})
    has_digit = any(ch.isdigit() for ch in normalized)
    uppercase_like = _is_uppercase_like(original)
    catid_like = _is_catid_like(normalized)
    numeric_code = bool(NUMERIC_CODE_RE.match(normalized)) and has_digit
    technical_like = normalized in TECHNICAL_TOKENS
    library_code_like = _is_library_code_token(normalized)
    vowel_ratio = _vowel_ratio(normalized)
    pack_suffix_like = (
        bool(PACK_SUFFIX_CODE_RE.match(normalized))
        and normalized not in COMMON_SUFFIX_WORDS
        and vowel_ratio <= 0.25
    )
    short_field_pack_code = _is_short_field_pack_code(normalized, distribution)
    pack_code_like = (
        normalized in PACK_CODE_TOKENS or pack_suffix_like or short_field_pack_code
    )
    code_prefix_like = _is_code_prefix_token(normalized)
    catid_like = catid_like or bool(distribution.get("cat_id") and code_prefix_like)
    low_vowel_ratio = len(normalized) >= 4 and vowel_ratio <= 0.15
    id_like = (
        catid_like
        or numeric_code
        or library_code_like
        or pack_code_like
        or code_prefix_like
        or (uppercase_like and len(normalized) <= 6)
    )

    reasons: list[str] = []
    decision = "keep"

    if not normalized or _is_basic_noise_token(normalized):
        decision = "filter"
        reasons.append("explicit_noise")
    elif normalized in EXPLICIT_STYLE_TOKENS:
        decision = "keep"
    elif normalized in STOPWORD_TOKENS:
        decision = "filter"
        reasons.append("explicit_noise")
    elif technical_like:
        decision = "filter"
        reasons.append("technical_term")
    elif normalized in LIBRARY_ABBREVIATION_TOKENS:
        decision = "filter"
        reasons.extend(["explicit_noise", "id_like"])
    elif library_code_like:
        decision = "filter"
        reasons.append("id_like")
    elif catid_like and normalized.startswith(("ds", "3ds")):
        decision = "filter"
        reasons.extend(["catid_like", "id_like"])
    elif catid_like:
        decision = "review"
        reasons.extend(["catid_like", "id_like"])
    elif numeric_code:
        decision = "review"
        reasons.extend(["numeric_code", "id_like"])
    elif pack_code_like:
        decision = "review"
        reasons.extend(["pack_code_like", "id_like"])
    elif code_prefix_like:
        decision = "review"
        reasons.extend(["code_prefix_like", "id_like"])
    elif len(normalized) == 2 and normalized.isalpha() and vowel_ratio == 0:
        decision = "review"
        reasons.append("id_like")
    elif low_vowel_ratio:
        decision = "review"
        reasons.append("low_vowel_ratio")
    elif uppercase_like and len(normalized) <= 6:
        decision = "review"
        reasons.append("id_like")

    if low_vowel_ratio and "low_vowel_ratio" not in reasons:
        reasons.append("low_vowel_ratio")
    if has_digit and decision != "keep" and "numeric_code" not in reasons and numeric_code:
        reasons.append("numeric_code")
    if technical_like and "technical_term" not in reasons:
        reasons.append("technical_term")

    reasons = _merge_reasons(reasons)
    return {
        "token": normalized,
        "decision": decision,
        "reasons": reasons,
        "vowel_ratio": round(vowel_ratio, 3),
        "has_digit": has_digit,
        "uppercase_like": uppercase_like,
        "catid_like": catid_like,
        "pack_code_like": pack_code_like,
        "code_prefix_like": code_prefix_like,
        "technical_like": technical_like,
        "field_distribution": distribution,
    }


def classify_phrase_quality(
    phrase: str, field_distribution: dict[str, int] | None = None
) -> dict[str, Any]:
    normalized = " ".join(_normalize_token(part) for part in phrase.split() if part.strip())
    tokens = [token for token in normalized.split() if token]
    distribution = dict(field_distribution or {})
    reasons: list[str] = []
    contains_noise_token = False
    contains_review_token = False
    id_like = False
    technical_like = normalized in TECHNICAL_PHRASES or any(
        blocked in normalized for blocked in TECHNICAL_PHRASES
    )

    if not tokens:
        return {
            "phrase": normalized,
            "decision": "filter",
            "reasons": ["explicit_noise"],
            "contains_noise_token": False,
            "technical_like": False,
            "id_like": False,
            "field_distribution": distribution,
        }

    if technical_like:
        reasons.append("technical_term")

    for token in tokens:
        quality = classify_token_quality(token)
        if quality["decision"] == "filter":
            contains_noise_token = True
            reasons.extend(quality["reasons"])
        elif quality["decision"] == "review":
            contains_review_token = True
            reasons.extend(quality["reasons"])
        if quality["catid_like"] or "id_like" in quality["reasons"]:
            id_like = True

    if contains_noise_token:
        reasons.append("phrase_contains_noise")

    if technical_like or contains_noise_token:
        decision = "filter"
    elif contains_review_token or id_like:
        decision = "review"
    else:
        decision = "keep"

    return {
        "phrase": normalized,
        "decision": decision,
        "reasons": _merge_reasons(reasons),
        "contains_noise_token": contains_noise_token,
        "technical_like": technical_like,
        "id_like": id_like,
        "field_distribution": distribution,
    }


def _is_library_code_token(token: str) -> bool:
    lower = token.lower()
    if DS_CODE_RE.match(lower) or THREE_DS_RE.match(lower):
        return True
    if not lower.isalpha() or len(lower) < 5:
        return False
    vowels = sum(ch in "aeiou" for ch in lower)
    ratio = vowels / len(lower)
    if ratio <= 0.30 and lower.startswith(LIBRARY_CODE_PREFIXES):
        return True
    return False


def _is_short_field_pack_code(token: str, field_distribution: dict[str, int]) -> bool:
    if not token.isalpha() or not 2 <= len(token) <= 4:
        return False
    return bool(
        field_distribution.get("filename")
        and field_distribution.get("keywords")
        and not any(
            field_distribution.get(field_name)
            for field_name in ("fx_name", "description", "category", "subcategory")
        )
    )


def _is_code_prefix_token(token: str) -> bool:
    lower = token.lower()
    for prefix, suffixes in CODE_PREFIX_SUFFIXES.items():
        if lower.startswith(prefix) and lower[len(prefix) :] in suffixes:
            return True
    return False


def _is_catid_like(token: str) -> bool:
    lower = token.lower()
    return bool(
        DS_CODE_RE.match(lower)
        or THREE_DS_RE.match(lower)
        or CATEGORY_CODE_RE.match(lower)
    )


def _is_uppercase_like(token: str) -> bool:
    letters = [ch for ch in token if ch.isalpha()]
    if len(letters) < 2:
        return False
    return all(ch.isupper() for ch in letters)


def _vowel_ratio(token: str) -> float:
    letters = [ch for ch in token.lower() if ch.isalpha()]
    if not letters:
        return 0.0
    vowels = sum(ch in "aeiou" for ch in letters)
    return vowels / len(letters)


def _normalize_token(token: str) -> str:
    return token.strip("-_ ").lower()


def _top_counter_rows(
    counter: Counter[str],
    filename_counter: Counter[str] | None = None,
    limit: int = 100,
) -> list[tuple[str, int, int]]:
    filename_counter = filename_counter or Counter()
    return [
        (token, freq, filename_counter.get(token, 0))
        for token, freq in counter.most_common(limit)
    ]


def _top_phrase_rows(
    phrase_counts: Counter[str],
    filename_phrase_counts: Counter[str] | None = None,
    limit: int = 100,
) -> list[tuple[str, int, int, int]]:
    filename_phrase_counts = filename_phrase_counts or Counter()
    rows: list[tuple[str, int, int, int]] = []
    for phrase, freq in phrase_counts.most_common(limit):
        rows.append((phrase, len(phrase.split()), freq, filename_phrase_counts.get(phrase, 0)))
    return rows


def _top_raw_phrase_rows_by_n(
    phrase_counts: Counter[str],
    limit: int = 100,
) -> dict[int, list[tuple]]:
    by_n: dict[int, list[tuple]] = {2: [], 3: [], 4: []}
    for n in (2, 3, 4):
        ranked = [
            (phrase, freq, 0)
            for phrase, freq in phrase_counts.items()
            if len(phrase.split()) == n
        ]
        ranked.sort(key=lambda item: (-item[1], item[0]))
        by_n[n] = ranked[:limit]
    return by_n


def _row_has_content(row: list[str]) -> bool:
    return any(str(cell).strip() for cell in row)


def _row_to_dict(headers: list[str], row: list[str]) -> dict[str, str]:
    width = max(len(headers), len(row))
    effective_headers = list(headers)
    while len(effective_headers) < width:
        effective_headers.append(f"col_{len(effective_headers) + 1}")
    out: dict[str, str] = {}
    for idx, header in enumerate(effective_headers):
        value = row[idx] if idx < len(row) else ""
        text = str(value).strip()
        if text:
            out[header] = text
    return out


def _cell_value(raw_dict: dict[str, str], column: str | None, col_index: dict[str, int]) -> str:
    if not column:
        return ""
    if column in raw_dict:
        return raw_dict[column]
    idx = col_index.get(column)
    if idx is None:
        return ""
    values = list(raw_dict.values())
    if idx < len(values):
        return values[idx]
    return ""


def _json_list(raw: str) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def write_reports(
    *,
    stats: ImportStats,
    db_path: Path,
    report_md: Path,
    report_csv: Path,
    noise_review_md: Path,
    field_coverage_md: Path,
    selected_files: list[str],
) -> None:
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_csv.parent.mkdir(parents=True, exist_ok=True)
    noise_review_md.parent.mkdir(parents=True, exist_ok=True)
    field_coverage_md.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        summary = load_database_summary(conn, stats, selected_files)
        clean_token_rows = _fetch_clean_token_rows(conn, 200)
        clean_phrase_rows_by_n = _fetch_clean_phrase_rows_by_n(conn, 200)
        filtered_token_rows = _fetch_filtered_token_rows(conn, 100)
        filtered_phrase_rows = _fetch_filtered_phrase_rows(conn, 100)
        review_rows = _fetch_review_rows(conn, 100)
        raw_token_rows = _top_counter_rows(
            stats.raw_token_counts, stats.raw_filename_token_counts, limit=100
        )
        raw_phrase_rows = _top_raw_phrase_rows_by_n(stats.raw_phrase_counts, limit=100)
        _write_import_csv(conn, report_csv)
        _write_noise_review_report(conn, noise_review_md)
        _write_field_coverage_report(conn, field_coverage_md, summary)

    md_lines = [
        "# BOOM FXName Style Corpus 0.2 Full Import Report",
        "",
        f"- generated_at: {_now()}",
        f"- database: `{db_path.as_posix()}`",
        f"- selected_files_this_run: **{len(selected_files)}**",
        "- weighting: fx_name x3, filename x2, description/keywords/category/subcategory x1",
        "- review policy: explicit noise is filtered; review items are excluded from scorer tables",
        "",
        "## Summary",
        "",
        "| metric | value |",
        "| --- | --- |",
        f"| total files selected | {summary['total_files_selected']} |",
        f"| imported files | {summary['imported_files']} |",
        f"| imported sheets | {summary['imported_sheets']} |",
        f"| fx_records | {summary['fx_records']} |",
        f"| skipped rows | {summary['skipped_rows']} |",
        f"| warnings count | {summary['warnings_count']} |",
        f"| failed files | {summary['failed_files']} |",
        f"| failed sheets | {summary['failed_sheets']} |",
        f"| duplicated source files count | {summary['duplicated_source_files']} |",
        "",
        "## Field recognition hit rate",
        "",
        "| field | hit_count | hit_rate |",
        "| --- | --- | --- |",
    ]
    for field_name in HIT_RATE_FIELDS:
        hits = summary["field_hit_rates"].get(field_name, (0, 0.0))
        md_lines.append(f"| {field_name} | {hits[0]} | {hits[1]:.1%} |")

    if stats.warnings:
        md_lines.extend(["", "## Current run warnings", ""])
        for warning in stats.warnings[:200]:
            md_lines.append(f"- {warning}")
        if len(stats.warnings) > 200:
            md_lines.append(f"- ... {len(stats.warnings) - 200} more warnings")

    md_lines.extend(
        [
            "",
            "## Top 200 clean style tokens",
            "",
            "| token | freq | filename_freq |",
            "| --- | --- | --- |",
        ]
    )
    for token, freq, filename_freq in clean_token_rows:
        md_lines.append(f"| {token} | {freq} | {filename_freq} |")

    for n in (2, 3, 4):
        md_lines.extend(
            [
                "",
                f"## Top 200 clean {n}-gram phrases",
                "",
                "| phrase | freq | filename_freq |",
                "| --- | --- | --- |",
            ]
        )
        for phrase, freq, filename_freq in clean_phrase_rows_by_n.get(n, []):
            md_lines.append(f"| {phrase} | {freq} | {filename_freq} |")

    md_lines.extend(
        [
            "",
            "## Top 100 raw tokens (unfiltered, for comparison)",
            "",
            "| token | freq | filename_freq |",
            "| --- | --- | --- |",
        ]
    )
    for token, freq, filename_freq in raw_token_rows:
        md_lines.append(f"| {token} | {freq} | {filename_freq} |")

    md_lines.extend(
        [
            "",
            "## Top 100 filtered-out tokens",
            "",
            "| token | freq | filename_freq | reasons |",
            "| --- | --- | --- | --- |",
        ]
    )
    for token, freq, filename_freq, reasons in filtered_token_rows:
        md_lines.append(f"| {token} | {freq} | {filename_freq} | {_format_reasons(reasons)} |")

    md_lines.extend(
        [
            "",
            "## Top 100 filtered-out phrases",
            "",
            "| phrase | n | freq | filename_freq | reasons |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for phrase, n, freq, filename_freq, reasons in filtered_phrase_rows:
        md_lines.append(
            f"| {phrase} | {n} | {freq} | {filename_freq} | {_format_reasons(reasons)} |"
        )

    md_lines.extend(
        [
            "",
            "## Top 100 review tokens / phrases",
            "",
            "| type | item | n | freq | filename_freq | reasons |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item_type, item, n, freq, filename_freq, reasons in review_rows:
        md_lines.append(
            f"| {item_type} | {item} | {n} | {freq} | {filename_freq} | "
            f"{_format_reasons(reasons)} |"
        )

    for n in (2, 3, 4):
        md_lines.extend(
            [
                "",
                f"## Top 100 raw {n}-gram phrases (unfiltered, for comparison)",
                "",
                "| phrase | freq | filename_freq |",
                "| --- | --- | --- |",
            ]
        )
        for phrase, freq, filename_freq in raw_phrase_rows.get(n, []):
            md_lines.append(f"| {phrase} | {freq} | {filename_freq} |")

    report_md.write_text("\n".join(md_lines), encoding="utf-8")


def load_database_summary(
    conn: sqlite3.Connection, stats: ImportStats, selected_files: list[str]
) -> dict[str, Any]:
    fx_records = conn.execute("SELECT COUNT(*) FROM fx_records").fetchone()[0]
    total = fx_records or 1
    field_hit_rates: dict[str, tuple[int, float]] = {}
    for field_name in HIT_RATE_FIELDS:
        hits = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM fx_records
            WHERE {field_name} IS NOT NULL AND TRIM({field_name}) != ''
            """
        ).fetchone()[0]
        field_hit_rates[field_name] = (hits, hits / total)

    run_totals = conn.execute(
        """
        SELECT
            COALESCE(SUM(selected_files), 0),
            COALESCE(SUM(skipped_rows), 0),
            COALESCE(SUM(duplicated_source_files), 0),
            COALESCE(SUM(failed_files), 0),
            COALESCE(SUM(failed_sheets), 0)
        FROM import_runs
        """
    ).fetchone()
    failed_files = conn.execute(
        "SELECT COUNT(*) FROM source_files WHERE status IN ('missing', 'error')"
    ).fetchone()[0]
    failed_sheets = conn.execute(
        "SELECT COUNT(*) FROM source_sheets WHERE status IN ('missing', 'error')"
    ).fetchone()[0]
    warnings_count = conn.execute("SELECT COUNT(*) FROM import_warnings").fetchone()[0]

    return {
        "total_files_selected": int(run_totals[0] or 0) or len(selected_files),
        "imported_files": conn.execute(
            "SELECT COUNT(*) FROM source_files WHERE status = 'ok'"
        ).fetchone()[0],
        "imported_sheets": conn.execute(
            "SELECT COUNT(*) FROM source_sheets WHERE status = 'ok'"
        ).fetchone()[0],
        "fx_records": fx_records,
        "skipped_rows": int(run_totals[1] or 0) or stats.skipped_rows,
        "warnings_count": int(warnings_count or len(stats.warnings)),
        "failed_files": int(failed_files or run_totals[3] or stats.failed_files),
        "failed_sheets": int(failed_sheets or run_totals[4] or stats.failed_sheets),
        "duplicated_source_files": int(run_totals[2] or 0) or stats.duplicated_source_files,
        "field_hit_rates": field_hit_rates,
    }


def _fetch_clean_token_rows(conn: sqlite3.Connection, limit: int) -> list[tuple[str, int, int]]:
    return conn.execute(
        """
        SELECT token, freq, filename_freq
        FROM tokens
        ORDER BY freq DESC, filename_freq DESC, token
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def _fetch_clean_phrase_rows_by_n(
    conn: sqlite3.Connection, limit: int
) -> dict[int, list[tuple[str, int, int]]]:
    rows: dict[int, list[tuple[str, int, int]]] = {}
    for n in (2, 3, 4):
        rows[n] = conn.execute(
            """
            SELECT phrase, freq, filename_freq
            FROM phrases
            WHERE n = ?
            ORDER BY freq DESC, filename_freq DESC, phrase
            LIMIT ?
            """,
            (n, limit),
        ).fetchall()
    return rows


def _fetch_filtered_token_rows(
    conn: sqlite3.Connection, limit: int
) -> list[tuple[str, int, int, str]]:
    return conn.execute(
        """
        SELECT token, freq, filename_freq, reasons
        FROM filtered_tokens
        ORDER BY freq DESC, filename_freq DESC, token
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def _fetch_filtered_phrase_rows(
    conn: sqlite3.Connection, limit: int
) -> list[tuple[str, int, int, int, str]]:
    return conn.execute(
        """
        SELECT phrase, n, freq, filename_freq, reasons
        FROM filtered_phrases
        ORDER BY freq DESC, filename_freq DESC, phrase
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def _fetch_review_rows(
    conn: sqlite3.Connection, limit: int
) -> list[tuple[str, str, int, int, int, str]]:
    return conn.execute(
        """
        SELECT item_type, item, n, freq, filename_freq, reasons
        FROM noise_review_items
        ORDER BY freq DESC, filename_freq DESC, item_type, item
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def _write_import_csv(conn: sqlite3.Connection, report_csv: Path) -> None:
    with report_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["file_path", "status", "sheets", "fx_records", "skipped_rows", "warnings"],
        )
        writer.writeheader()
        for row in conn.execute(
            """
            SELECT file_path, status, sheet_count, fx_record_count, skipped_row_count, warnings
            FROM source_files
            ORDER BY file_path
            """
        ):
            writer.writerow(
                {
                    "file_path": row[0],
                    "status": row[1],
                    "sheets": row[2],
                    "fx_records": row[3],
                    "skipped_rows": row[4],
                    "warnings": row[5] or "[]",
                }
            )


def _write_noise_review_report(conn: sqlite3.Connection, path: Path) -> None:
    lines = [
        "# BOOM Style Noise Review",
        "",
        f"- generated_at: {_now()}",
        "- policy: review items are excluded from scorer tables and not added to manual noise rules automatically",
        "",
        "## Top review tokens",
        "",
        "| token | freq | filename_freq | reasons | field_distribution |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item, freq, filename_freq, reasons, details_json in conn.execute(
        """
        SELECT item, freq, filename_freq, reasons, details_json
        FROM noise_review_items
        WHERE item_type = 'token'
        ORDER BY freq DESC, filename_freq DESC, item
        LIMIT 200
        """
    ):
        details = _json_dict(details_json)
        lines.append(
            f"| {item} | {freq} | {filename_freq} | {_format_reasons(reasons)} | "
            f"{_format_distribution(details.get('field_distribution', {}))} |"
        )

    lines.extend(
        [
            "",
            "## Top review phrases",
            "",
            "| phrase | n | freq | filename_freq | reasons | field_distribution |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item, n, freq, filename_freq, reasons, details_json in conn.execute(
        """
        SELECT item, n, freq, filename_freq, reasons, details_json
        FROM noise_review_items
        WHERE item_type = 'phrase'
        ORDER BY freq DESC, filename_freq DESC, item
        LIMIT 200
        """
    ):
        details = _json_dict(details_json)
        lines.append(
            f"| {item} | {n} | {freq} | {filename_freq} | {_format_reasons(reasons)} | "
            f"{_format_distribution(details.get('field_distribution', {}))} |"
        )

    lines.extend(
        [
            "",
            "## Top filtered tokens",
            "",
            "| token | freq | filename_freq | reasons |",
            "| --- | --- | --- | --- |",
        ]
    )
    for token, freq, filename_freq, reasons in _fetch_filtered_token_rows(conn, 200):
        lines.append(f"| {token} | {freq} | {filename_freq} | {_format_reasons(reasons)} |")

    lines.extend(
        [
            "",
            "## Top filtered phrases",
            "",
            "| phrase | n | freq | filename_freq | reasons |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for phrase, n, freq, filename_freq, reasons in _fetch_filtered_phrase_rows(conn, 200):
        lines.append(
            f"| {phrase} | {n} | {freq} | {filename_freq} | {_format_reasons(reasons)} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_field_coverage_report(
    conn: sqlite3.Connection, path: Path, summary: dict[str, Any]
) -> None:
    lines = [
        "# BOOM Style Field Coverage",
        "",
        f"- generated_at: {_now()}",
        f"- fx_records: {summary['fx_records']}",
        "",
        "## Record field hit rate",
        "",
        "| field | hit_count | hit_rate |",
        "| --- | --- | --- |",
    ]
    for field_name in HIT_RATE_FIELDS:
        hits, rate = summary["field_hit_rates"].get(field_name, (0, 0.0))
        lines.append(f"| {field_name} | {hits} | {rate:.1%} |")

    lines.extend(
        [
            "",
            "## Top token field stats",
            "",
            "| token | field | raw_freq | weighted_freq |",
            "| --- | --- | --- | --- |",
        ]
    )
    for token, field_name, raw_freq, weighted_freq in conn.execute(
        """
        SELECT token, field_name, raw_freq, weighted_freq
        FROM token_field_stats
        ORDER BY weighted_freq DESC, raw_freq DESC, token, field_name
        LIMIT 300
        """
    ):
        lines.append(f"| {token} | {field_name} | {raw_freq} | {weighted_freq} |")

    lines.extend(
        [
            "",
            "## Top phrase field stats",
            "",
            "| phrase | field | raw_freq | weighted_freq |",
            "| --- | --- | --- | --- |",
        ]
    )
    for phrase, field_name, raw_freq, weighted_freq in conn.execute(
        """
        SELECT phrase, field_name, raw_freq, weighted_freq
        FROM phrase_field_stats
        ORDER BY weighted_freq DESC, raw_freq DESC, phrase, field_name
        LIMIT 300
        """
    ):
        lines.append(f"| {phrase} | {field_name} | {raw_freq} | {weighted_freq} |")
    path.write_text("\n".join(lines), encoding="utf-8")


def _format_reasons(raw: str) -> str:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return raw
    if isinstance(data, list):
        return ", ".join(str(item) for item in data)
    return str(data)


def _format_distribution(distribution: dict[str, Any]) -> str:
    if not distribution:
        return ""
    return ", ".join(
        f"{field}:{count}" for field, count in sorted(distribution.items(), key=lambda item: item[0])
    )


def _json_dict(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    raise SystemExit(main())
