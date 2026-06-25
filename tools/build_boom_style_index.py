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
from collections import Counter
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

STAT_FIELDS = ("filename", "fx_name", "description", "keywords", "category", "subcategory")
HIT_RATE_FIELDS = ("filename", "fx_name", "description", "category", "keywords", "cat_id")

NOISE_TOKENS = {
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
    imported_files: int = 0
    imported_sheets: int = 0
    imported_fx_records: int = 0
    skipped_rows: int = 0
    warnings: list[str] = field(default_factory=list)
    field_hits: Counter[str] = field(default_factory=Counter)
    file_rows: list[dict[str, Any]] = field(default_factory=list)


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
    args = parser.parse_args()

    root = Path(args.root)
    inventory_path = Path(args.inventory)
    db_path = Path(args.db)
    report_md = Path(args.report_md)
    report_csv = Path(args.report_csv)

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

    token_rows, phrase_rows = load_token_phrase_stats(db_path)
    write_reports(
        stats=stats,
        db_path=db_path,
        report_md=report_md,
        report_csv=report_csv,
        selected_files=selected_files,
        token_rows=token_rows,
        phrase_rows=phrase_rows,
    )

    print(f"Root: {root}")
    print(f"Selected files: {len(selected_files)}")
    print(f"Imported sheets: {stats.imported_sheets}")
    print(f"FX records: {stats.imported_fx_records}")
    print(f"Skipped rows: {stats.skipped_rows}")
    print(f"Warnings: {len(stats.warnings)}")
    print(f"Database: {db_path}")
    print(f"Report: {report_md}")
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
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        if rebuild:
            create_schema(conn)
        else:
            ensure_schema(conn)

        run_id = conn.execute(
            """
            INSERT INTO import_runs (
                started_at, root_path, inventory_path, offset_files, limit_files, rebuild
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                _now(),
                root.as_posix(),
                inventory_path.as_posix(),
                offset_files,
                limit_files,
                int(rebuild),
            ),
        ).lastrowid

        token_counts: Counter[str] = Counter()
        filename_token_counts: Counter[str] = Counter()
        phrase_counts: Counter[str] = Counter()
        filename_phrase_counts: Counter[str] = Counter()

        for rel_file in selected_files:
            file_path = root / rel_file
            file_warnings: list[str] = []
            file_fx_count = 0
            file_skipped = 0
            file_sheet_count = 0

            if not file_path.is_file():
                warn = f"{rel_file}: file not found"
                stats.warnings.append(warn)
                file_warnings.append(warn)
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
                    conn.execute(
                        """
                        INSERT INTO source_sheets (file_id, sheet_name, row_count, status, warnings)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (file_id, sheet_name, 0, "missing", json.dumps(sheet_warnings)),
                    )
                    continue

                sheet_warnings.extend(sheet_data.warnings)
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
                        token_counts=token_counts,
                        filename_token_counts=filename_token_counts,
                        phrase_counts=phrase_counts,
                        filename_phrase_counts=filename_phrase_counts,
                    )
                except Exception as exc:  # noqa: BLE001
                    warn = f"{rel_file}/{sheet_name}: import failed: {exc}"
                    stats.warnings.append(warn)
                    sheet_warnings.append(warn)
                    conn.execute(
                        "UPDATE source_sheets SET status = ?, warnings = ? WHERE id = ?",
                        ("error", json.dumps(sheet_warnings), sheet_id),
                    )
                    continue

                stats.warnings.extend(sheet_warns)
                file_fx_count += sheet_fx
                file_skipped += sheet_skipped

            if file_warnings:
                conn.execute(
                    "UPDATE source_files SET warnings = ? WHERE id = ?",
                    (json.dumps(file_warnings), file_id),
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

        write_token_phrase_tables(
            conn, token_counts, filename_token_counts, phrase_counts, filename_phrase_counts
        )
        conn.execute(
            "UPDATE import_runs SET finished_at = ? WHERE id = ?",
            (_now(), run_id),
        )

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
    token_counts: Counter[str],
    filename_token_counts: Counter[str],
    phrase_counts: Counter[str],
    filename_phrase_counts: Counter[str],
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
        _accumulate_text_stats(record, token_counts, filename_token_counts, phrase_counts, filename_phrase_counts)

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
            rebuild INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS source_files (
            id INTEGER PRIMARY KEY,
            run_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            status TEXT NOT NULL,
            warnings TEXT,
            FOREIGN KEY (run_id) REFERENCES import_runs(id)
        );
        CREATE TABLE IF NOT EXISTS source_sheets (
            id INTEGER PRIMARY KEY,
            file_id INTEGER NOT NULL,
            sheet_name TEXT NOT NULL,
            row_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
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
        CREATE INDEX IF NOT EXISTS idx_fx_records_source ON fx_records(source_file, sheet_name);
        CREATE INDEX IF NOT EXISTS idx_phrases_weight ON phrases(freq, filename_freq);
        CREATE INDEX IF NOT EXISTS idx_phrases_n ON phrases(n);
        """
    )


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


def write_reports(
    *,
    stats: ImportStats,
    db_path: Path,
    report_md: Path,
    report_csv: Path,
    selected_files: list[str],
    token_rows: list[tuple],
    phrase_rows: dict[int, list[tuple]],
) -> None:
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_csv.parent.mkdir(parents=True, exist_ok=True)

    hit_rates = _field_hit_rates(stats)
    generated = _now()

    md_lines = [
        "# BOOM FXName Style Corpus 0.1B Import Report",
        "",
        f"- 生成时间：{generated}",
        f"- 数据库：`{db_path.as_posix()}`",
        f"- 选中文件数：**{len(selected_files)}**",
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

    md_lines.extend(["", "## Top 100 tokens", "", "| token | freq | filename_freq |", "| --- | --- | --- |"])
    for token, freq, filename_freq in token_rows:
        md_lines.append(f"| {token} | {freq} | {filename_freq} |")

    for n in (2, 3, 4):
        md_lines.extend(
            [
                "",
                f"## Top 100 {n}-gram phrases",
                "",
                "| phrase | freq | filename_freq |",
                "| --- | --- | --- |",
            ]
        )
        for phrase, freq, filename_freq in phrase_rows.get(n, []):
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
    token_counts: Counter[str],
    filename_token_counts: Counter[str],
    phrase_counts: Counter[str],
    filename_phrase_counts: Counter[str],
) -> None:
    for field_name in STAT_FIELDS:
        text = str(record.get(field_name) or "")
        if not text.strip():
            continue
        tokens = _extract_tokens(text)
        if not tokens:
            continue
        token_counts.update(tokens)
        if field_name == "filename":
            filename_token_counts.update(tokens)
        for phrase in _extract_phrases(tokens):
            phrase_counts[phrase] += 1
            if field_name == "filename":
                filename_phrase_counts[phrase] += 1


def _extract_tokens(text: str) -> list[str]:
    tokens = [_normalize_token(word) for word in WORD_RE.findall(text)]
    return [token for token in tokens if token and not _is_noise_token(token)]


def _extract_phrases(tokens: list[str]) -> Iterable[str]:
    for n in range(2, 5):
        for i in range(0, len(tokens) - n + 1):
            yield " ".join(tokens[i : i + n])


def _normalize_token(token: str) -> str:
    return token.strip("-_ ").lower()


def _is_noise_token(token: str) -> bool:
    if len(token) <= 1:
        return True
    if token.isdigit():
        return True
    return token in NOISE_TOKENS


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


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    raise SystemExit(main())
