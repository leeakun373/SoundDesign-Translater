#!/usr/bin/env python3
"""Export BOOM metadata CSV/XLSX files into a trusted, queryable corpus."""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.inventory_boom_excel import (  # noqa: E402
    _iter_ooxml_sheets,
    _read_xlsx_rows,
    _read_xlsx_shared_strings,
)


DEFAULT_DB = ROOT / "data" / "boomone" / "boomone_records.sqlite"
DEFAULT_UCS_DIR = ROOT / "exports" / "boomone_by_ucs"
DEFAULT_REPORT = ROOT / "reports" / "boomone_coverage.md"
RECORD_COLUMNS = (
    "library",
    "filename",
    "fx_name",
    "description",
    "cat_id",
    "category",
    "subcategory",
    "category_full",
    "vendor_category",
    "keywords",
    "microphone",
    "source_file",
)
CSV_EXPORT_COLUMNS = ("record_id", *RECORD_COLUMNS)


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().casefold())


HEADER_ALIASES = {
    "library": {"library", "libraryname", "collection", "collectionname"},
    "filename": {
        "filename",
        "file",
        "filepath",
        "audiofile",
        "soundfile",
        "wav",
        "wave",
    },
    "fx_name": {
        "fxname",
        "soundname",
        "effectname",
        "sfxname",
        "title",
        "name",
    },
    "description": {
        "description",
        "desc",
        "comment",
        "comments",
        "notes",
        "longdescription",
    },
    "cat_id": {"catid", "categoryid", "ucscatid", "ucsid"},
    "category": {"category", "ucscategory", "maincategory"},
    "subcategory": {
        "subcategory",
        "subcat",
        "ucssubcategory",
        "sub category",
    },
    "category_full": {
        "categoryfull",
        "fullcategory",
        "categorypath",
        "ucscategoryfull",
    },
    "vendor_category": {
        "vendorcategory",
        "originalcategory",
        "boomcategory",
    },
    "keywords": {"keywords", "keyword", "tags", "searchterms"},
    "microphone": {
        "microphone",
        "microphones",
        "mic",
        "mics",
        "recordingmicrophone",
    },
}
NORMALIZED_ALIASES = {
    target: {_normalize_header(alias) for alias in aliases}
    for target, aliases in HEADER_ALIASES.items()
}


@dataclass(frozen=True)
class ExportSummary:
    source_files: int
    source_sheets: int
    records: int
    skipped_rows: int
    warnings: tuple[str, ...]
    field_counts: dict[str, int]


def export_corpus(
    input_dir: Path,
    db_path: Path = DEFAULT_DB,
    ucs_dir: Path = DEFAULT_UCS_DIR,
    report_path: Path = DEFAULT_REPORT,
) -> ExportSummary:
    """Build corpus artifacts without changing source metadata or canonical data."""
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        raise NotADirectoryError(f"BOOM metadata directory not found: {input_dir}")

    warnings: list[str] = []
    records: list[dict[str, str]] = []
    source_files = 0
    source_sheets = 0
    skipped_rows = 0
    paths = sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".csv", ".xlsx", ".xlsm"}
    )
    for path in paths:
        source_files += 1
        try:
            tables = list(_read_source_tables(path, input_dir))
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            warnings.append(f"{path.relative_to(input_dir)}: {exc}")
            continue
        source_sheets += len(tables)
        for source_name, rows in tables:
            table_records, table_skipped, table_warnings = _map_table(
                rows, source_name, path.stem
            )
            records.extend(table_records)
            skipped_rows += table_skipped
            warnings.extend(table_warnings)

    inserted = _write_sqlite(records, Path(db_path))
    _write_ucs_exports(inserted, Path(ucs_dir))
    field_counts = {
        column: sum(bool(row[column]) for row in records)
        for column in RECORD_COLUMNS
    }
    summary = ExportSummary(
        source_files=source_files,
        source_sheets=source_sheets,
        records=len(records),
        skipped_rows=skipped_rows,
        warnings=tuple(warnings),
        field_counts=field_counts,
    )
    _write_coverage_report(summary, input_dir, Path(db_path), Path(report_path))
    return summary


def _read_source_tables(
    path: Path, root: Path
) -> Iterator[tuple[str, list[list[str]]]]:
    relative = path.relative_to(root).as_posix()
    if path.suffix.lower() == ".csv":
        yield relative, _read_csv_rows(path)
        return
    with zipfile.ZipFile(path) as archive:
        shared = _read_xlsx_shared_strings(archive)
        for sheet_name, xml_path in _iter_ooxml_sheets(archive):
            yield f"{relative}#{sheet_name}", _read_xlsx_rows(
                archive, xml_path, shared
            )


def _read_csv_rows(path: Path) -> list[list[str]]:
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            text = path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        try:
            dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        return [
            [str(value).strip() for value in row]
            for row in csv.reader(text.splitlines(), dialect)
        ]
    raise ValueError(f"unsupported CSV encoding: {last_error}")


def _map_table(
    rows: list[list[str]], source_name: str, default_library: str
) -> tuple[list[dict[str, str]], int, list[str]]:
    warnings: list[str] = []
    if not rows:
        return [], 0, [f"{source_name}: empty table"]
    header_index = _find_header_row(rows)
    headers = rows[header_index]
    mapping = _map_headers(headers)
    if not mapping:
        return [], max(0, len(rows) - header_index - 1), [
            f"{source_name}: no recognized metadata columns"
        ]
    if not ({"filename", "fx_name", "description"} & set(mapping)):
        warnings.append(
            f"{source_name}: no filename/fx_name/description column; metadata-only rows kept"
        )

    output: list[dict[str, str]] = []
    skipped = 0
    for source_row in rows[header_index + 1 :]:
        record = {column: "" for column in RECORD_COLUMNS}
        for target, column_index in mapping.items():
            if column_index < len(source_row):
                record[target] = str(source_row[column_index]).strip()
        record["library"] = record["library"] or default_library
        record["category_full"] = record["category_full"] or _category_full(record)
        record["source_file"] = source_name
        if not any(record[column] for column in RECORD_COLUMNS[:-1]):
            skipped += 1
            continue
        output.append(record)
    return output, skipped, warnings


def _find_header_row(rows: list[list[str]]) -> int:
    best_index = 0
    best_score = -1
    for index, row in enumerate(rows[:20]):
        normalized = {_normalize_header(value) for value in row if str(value).strip()}
        score = sum(
            bool(normalized & aliases) for aliases in NORMALIZED_ALIASES.values()
        )
        if score > best_score:
            best_index = index
            best_score = score
    return best_index


def _map_headers(headers: list[str]) -> dict[str, int]:
    mapped: dict[str, int] = {}
    for index, header in enumerate(headers):
        normalized = _normalize_header(str(header))
        for target, aliases in NORMALIZED_ALIASES.items():
            if target not in mapped and normalized in aliases:
                mapped[target] = index
                break
    return mapped


def _category_full(record: dict[str, str]) -> str:
    return " > ".join(
        value for value in (record["category"], record["subcategory"]) if value
    )


def _write_sqlite(
    records: list[dict[str, str]], db_path: Path
) -> list[dict[str, str | int]]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            DROP TABLE IF EXISTS boomone_records;
            CREATE TABLE boomone_records (
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                library TEXT NOT NULL DEFAULT '',
                filename TEXT NOT NULL DEFAULT '',
                fx_name TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                cat_id TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                subcategory TEXT NOT NULL DEFAULT '',
                category_full TEXT NOT NULL DEFAULT '',
                vendor_category TEXT NOT NULL DEFAULT '',
                keywords TEXT NOT NULL DEFAULT '',
                microphone TEXT NOT NULL DEFAULT '',
                source_file TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX idx_boomone_cat_id ON boomone_records(cat_id);
            CREATE INDEX idx_boomone_category ON boomone_records(category, subcategory);
            CREATE INDEX idx_boomone_source ON boomone_records(source_file);
            """
        )
        placeholders = ",".join("?" for _ in RECORD_COLUMNS)
        connection.executemany(
            f"INSERT INTO boomone_records ({','.join(RECORD_COLUMNS)}) "
            f"VALUES ({placeholders})",
            ([record[column] for column in RECORD_COLUMNS] for record in records),
        )
        connection.commit()
        rows = connection.execute(
            f"SELECT record_id,{','.join(RECORD_COLUMNS)} "
            "FROM boomone_records ORDER BY record_id"
        ).fetchall()
    finally:
        connection.close()
    return [dict(zip(CSV_EXPORT_COLUMNS, row)) for row in rows]


def _write_ucs_exports(
    rows: list[dict[str, str | int]], output_dir: Path
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("*.csv"):
        stale.unlink()
    grouped: dict[str, list[dict[str, str | int]]] = defaultdict(list)
    for row in rows:
        group = str(row["category"] or row["vendor_category"] or "uncategorized")
        grouped[group].append(row)
    used_names: Counter[str] = Counter()
    for group, group_rows in sorted(grouped.items()):
        stem = _safe_filename(group)
        used_names[stem] += 1
        if used_names[stem] > 1:
            stem = f"{stem}_{used_names[stem]}"
        with (output_dir / f"{stem}.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_EXPORT_COLUMNS)
            writer.writeheader()
            writer.writerows(group_rows)


def _write_coverage_report(
    summary: ExportSummary,
    input_dir: Path,
    db_path: Path,
    report_path: Path,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# BOOMOne Corpus Coverage",
        "",
        f"- input: `{input_dir}`",
        f"- sqlite: `{db_path}`",
        f"- source_files: `{summary.source_files}`",
        f"- source_sheets: `{summary.source_sheets}`",
        f"- records: `{summary.records}`",
        f"- skipped_rows: `{summary.skipped_rows}`",
        f"- warning_count: `{len(summary.warnings)}`",
        "",
        "## Field coverage",
        "",
        "| field | populated | coverage |",
        "| --- | ---: | ---: |",
    ]
    for field_name in RECORD_COLUMNS:
        count = summary.field_counts[field_name]
        coverage = count / summary.records if summary.records else 0.0
        lines.append(f"| {field_name} | {count} | {coverage:.1%} |")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in summary.warnings)
    if not summary.warnings:
        lines.append("- none")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_")
    return cleaned[:80] or "uncategorized"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--ucs-dir", type=Path, default=DEFAULT_UCS_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    try:
        summary = export_corpus(args.input_dir, args.db, args.ucs_dir, args.report)
    except NotADirectoryError as exc:
        parser.error(str(exc))
    print(
        f"files={summary.source_files} sheets={summary.source_sheets} "
        f"records={summary.records} warnings={len(summary.warnings)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
