#!/usr/bin/env python3
"""BOOM Excel Metadata Corpus 0.1A — recursive Excel inventory scanner."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_ROOT = ROOT / "docs" / "训练数据"
DEFAULT_MD = ROOT / "tests" / "results" / "boom_metadata_inventory.md"
DEFAULT_CSV = ROOT / "tests" / "results" / "boom_metadata_inventory.csv"
EXCEL_EXTS = {".xlsx", ".xlsm", ".xls"}
OOXML_EXTS = {".xlsx", ".xlsm"}
SAMPLE_TRUNCATE = 120
MAX_SAMPLE_ROWS = 3

OOXML_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

ROLE_PATTERNS: dict[str, tuple[str, ...]] = {
    "filename-like": (
        "filename",
        "file_name",
        "filepath",
        "file_path",
        "audio_file",
        "wav",
        "wave",
    ),
    "fxname-like": (
        "fxname",
        "fx_name",
        "sound_name",
        "effect_name",
        "sfx_name",
        "fx",
    ),
    "description-like": (
        "description",
        "desc",
        "bwdescription",
        "long_description",
        "note",
        "notes",
        "comment",
        "comments",
    ),
    "category-like": ("category", "main_category", "cat"),
    "subcategory-like": ("subcategory", "sub_category", "subcat", "sub_cat"),
    "keywords-like": ("keywords", "keyword", "tags", "tag"),
    "catid-like": ("catid", "cat_id", "category_id", "categoryid"),
    "library-like": ("library", "lib", "collection", "pack", "sound_library"),
    "microphone-like": ("microphone", "mic", "mics", "mic_type", "microphones"),
}

ROLE_ORDER = tuple(ROLE_PATTERNS.keys())


@dataclass
class SheetInventory:
    file_path: str
    file_name: str
    sheet_name: str
    row_count: int
    column_count: int
    headers: list[str] = field(default_factory=list)
    guessed_columns: dict[str, list[str]] = field(default_factory=dict)
    sample_rows: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="root directory to scan")
    parser.add_argument("--md", default=str(DEFAULT_MD), help="markdown report path")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="csv report path")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"ERROR: root directory not found: {root}", file=sys.stderr)
        return 1

    records = scan_directory(root)
    md_path = Path(args.md)
    csv_path = Path(args.csv)
    write_markdown(records, md_path, root)
    write_csv(records, csv_path)

    file_count = len({r.file_path for r in records})
    warn_count = sum(len(r.warnings) for r in records)
    print(f"Root: {root}")
    print(f"Excel files: {file_count}")
    print(f"Sheets inventoried: {len(records)}")
    print(f"Warnings: {warn_count}")
    print(f"Markdown: {md_path}")
    print(f"CSV: {csv_path}")
    return 0


def scan_directory(root: Path) -> list[SheetInventory]:
    records: list[SheetInventory] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in EXCEL_EXTS:
            continue
        records.extend(scan_file(path, root))
    return records


def scan_file(path: Path, root: Path) -> list[SheetInventory]:
    suffix = path.suffix.lower()
    rel_path = _relative_path(path, root)
    try:
        if suffix in OOXML_EXTS:
            return _read_ooxml_workbook(path, rel_path)
        if suffix == ".xls":
            return _read_xls_workbook(path, rel_path)
    except Exception as exc:  # noqa: BLE001 — inventory must survive bad files
        return [
            SheetInventory(
                file_path=rel_path,
                file_name=path.name,
                sheet_name="(file-level)",
                row_count=0,
                column_count=0,
                warnings=[f"failed to read workbook: {exc}"],
            )
        ]
    return []


def _read_ooxml_workbook(path: Path, rel_path: str) -> list[SheetInventory]:
    records: list[SheetInventory] = []
    with zipfile.ZipFile(path) as zf:
        shared = _read_xlsx_shared_strings(zf)
        for sheet_name, sheet_xml in _iter_ooxml_sheets(zf):
            warnings: list[str] = []
            try:
                rows = [_pad_row(row) for row in _read_xlsx_rows(zf, sheet_xml, shared)]
            except Exception as exc:  # noqa: BLE001
                records.append(
                    SheetInventory(
                        file_path=rel_path,
                        file_name=path.name,
                        sheet_name=sheet_name,
                        row_count=0,
                        column_count=0,
                        warnings=[f"failed to read sheet: {exc}"],
                    )
                )
                continue

            if not rows:
                records.append(
                    SheetInventory(
                        file_path=rel_path,
                        file_name=path.name,
                        sheet_name=sheet_name,
                        row_count=0,
                        column_count=0,
                        warnings=["empty sheet"],
                    )
                )
                continue

            records.append(_build_sheet_inventory(rel_path, path.name, sheet_name, rows, warnings))
    if not records:
        records.append(
            SheetInventory(
                file_path=rel_path,
                file_name=path.name,
                sheet_name="(workbook)",
                row_count=0,
                column_count=0,
                warnings=["no sheets found"],
            )
        )
    return records


def _read_xls_workbook(path: Path, rel_path: str) -> list[SheetInventory]:
    try:
        import xlrd
    except ImportError:
        return [
            SheetInventory(
                file_path=rel_path,
                file_name=path.name,
                sheet_name="(file-level)",
                row_count=0,
                column_count=0,
                warnings=[".xls support unavailable: xlrd not installed"],
            )
        ]

    records: list[SheetInventory] = []
    try:
        workbook = xlrd.open_workbook(str(path), on_demand=True)
    except Exception as exc:  # noqa: BLE001
        return [
            SheetInventory(
                file_path=rel_path,
                file_name=path.name,
                sheet_name="(file-level)",
                row_count=0,
                column_count=0,
                warnings=[f"failed to read .xls workbook: {exc}"],
            )
        ]

    try:
        for index in range(workbook.nsheets):
            sheet_name = workbook.sheet_names()[index]
            warnings: list[str] = []
            try:
                sheet = workbook.sheet_by_index(index)
                rows = [_xls_row_values(sheet, row_idx) for row_idx in range(sheet.nrows)]
            except Exception as exc:  # noqa: BLE001
                records.append(
                    SheetInventory(
                        file_path=rel_path,
                        file_name=path.name,
                        sheet_name=sheet_name,
                        row_count=0,
                        column_count=0,
                        warnings=[f"failed to read sheet: {exc}"],
                    )
                )
                continue

            if not rows:
                records.append(
                    SheetInventory(
                        file_path=rel_path,
                        file_name=path.name,
                        sheet_name=sheet_name,
                        row_count=0,
                        column_count=0,
                        warnings=["empty sheet"],
                    )
                )
                continue

            records.append(_build_sheet_inventory(rel_path, path.name, sheet_name, rows, warnings))
    finally:
        workbook.release_resources()

    if not records:
        records.append(
            SheetInventory(
                file_path=rel_path,
                file_name=path.name,
                sheet_name="(workbook)",
                row_count=0,
                column_count=0,
                warnings=["no sheets found"],
            )
        )
    return records


def _build_sheet_inventory(
    rel_path: str,
    file_name: str,
    sheet_name: str,
    rows: list[list[str]],
    warnings: list[str],
) -> SheetInventory:
    row_count = len(rows)
    column_count = max((len(row) for row in rows), default=0)
    headers = _extract_headers(rows, warnings)
    guessed = guess_useful_columns(headers)
    sample_rows = _sample_data_rows(rows, headers)

    if row_count <= 1 and not sample_rows:
        warnings.append("no data rows detected")

    return SheetInventory(
        file_path=rel_path,
        file_name=file_name,
        sheet_name=sheet_name,
        row_count=row_count,
        column_count=column_count,
        headers=headers,
        guessed_columns=guessed,
        sample_rows=sample_rows,
        warnings=warnings,
    )


def _extract_headers(rows: list[list[str]], warnings: list[str]) -> list[str]:
    if not rows:
        return []
    headers = [str(cell).strip() for cell in rows[0]]
    if not any(headers):
        warnings.append("header row appears empty; using column indexes")
        width = max(len(rows[0]), max((len(row) for row in rows), default=0))
        return [f"col_{idx + 1}" for idx in range(width)]
    if len(set(h for h in headers if h)) < len([h for h in headers if h]):
        warnings.append("duplicate header names detected")
    return headers


def guess_useful_columns(headers: list[str]) -> dict[str, list[str]]:
    guessed = {role: [] for role in ROLE_ORDER}
    for header in headers:
        if not header:
            continue
        roles = _guess_roles_for_header(header)
        for role in roles:
            guessed[role].append(header)
    return guessed


def _guess_roles_for_header(header: str) -> list[str]:
    normalized = _normalize_header(header)
    if not normalized:
        return []

    matched: list[str] = []
    for role in ROLE_ORDER:
        if _header_matches_role(normalized, role):
            matched.append(role)

    if not matched and normalized in {"file", "name", "title"}:
        matched.append("filename-like" if normalized == "file" else "fxname-like")
    return matched


def _token_match(normalized: str, token: str) -> bool:
    return (
        normalized == token
        or normalized.endswith(f"_{token}")
        or normalized.startswith(f"{token}_")
    )


def _header_matches_role(normalized: str, role: str) -> bool:
    if role == "subcategory-like":
        return any(_token_match(normalized, token) for token in ROLE_PATTERNS[role])

    if role == "category-like":
        if any(_token_match(normalized, token) for token in ROLE_PATTERNS["subcategory-like"]):
            return False
        return any(_token_match(normalized, token) for token in ROLE_PATTERNS[role])

    if role == "filename-like":
        if normalized in {"name", "title"}:
            return False
        return any(_token_match(normalized, token) for token in ROLE_PATTERNS[role]) or normalized == "file"

    if role == "fxname-like":
        return any(_token_match(normalized, token) for token in ROLE_PATTERNS[role]) or normalized in {
            "name",
            "title",
        }

    return any(_token_match(normalized, token) for token in ROLE_PATTERNS[role])


def _sample_data_rows(rows: list[list[str]], headers: list[str]) -> list[dict[str, str]]:
    if len(rows) <= 1:
        return []

    width = max(len(headers), max((len(row) for row in rows), default=0))
    effective_headers = headers[:width]
    while len(effective_headers) < width:
        effective_headers.append(f"col_{len(effective_headers) + 1}")

    samples: list[dict[str, str]] = []
    for row in rows[1:]:
        if not _row_has_content(row):
            continue
        record: dict[str, str] = {}
        for idx, header in enumerate(effective_headers):
            value = row[idx] if idx < len(row) else ""
            text = _truncate(str(value).strip())
            if text:
                record[header] = text
        if record:
            samples.append(record)
        if len(samples) >= MAX_SAMPLE_ROWS:
            break
    return samples


def _row_has_content(row: list[str]) -> bool:
    return any(str(cell).strip() for cell in row)


def _normalize_header(header: str) -> str:
    text = header.strip().lower()
    text = re.sub(r"[\s\-]+", "_", text)
    text = re.sub(r"[^a-z0-9_]+", "", text)
    return text


def _truncate(value: str, limit: int = SAMPLE_TRUNCATE) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _pad_row(row: list[str]) -> list[str]:
    return [str(cell) if cell is not None else "" for cell in row]


def _xls_row_values(sheet: Any, row_idx: int) -> list[str]:
    values: list[str] = []
    for col_idx in range(sheet.ncols):
        cell = sheet.cell(row_idx, col_idx)
        if cell.ctype == 2 and float(cell.value).is_integer():
            values.append(str(int(cell.value)))
        else:
            values.append(str(cell.value).strip() if cell.value is not None else "")
    return values


def _iter_ooxml_sheets(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels_path = "xl/_rels/workbook.xml.rels"
    if rels_path not in zf.namelist():
        return [(name, name) for name in zf.namelist() if name.startswith("xl/worksheets/sheet")]

    rels = ET.fromstring(zf.read(rels_path))
    rid_to_target = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall(f"{PKG_REL_NS}Relationship")
    }

    sheets: list[tuple[str, str]] = []
    for sheet in workbook.findall(f".//{OOXML_NS}sheet"):
        name = sheet.attrib.get("name", "sheet")
        rid = sheet.attrib.get(f"{REL_NS}id")
        target = rid_to_target.get(rid or "", "")
        if not target:
            continue
        xml_path = target if target.startswith("xl/") else f"xl/{target}"
        if xml_path in zf.namelist():
            sheets.append((name, xml_path))
    return sheets


def _read_xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for si in root.findall(f"{OOXML_NS}si"):
        pieces = [node.text or "" for node in si.iter(f"{OOXML_NS}t")]
        strings.append("".join(pieces))
    return strings


def _read_xlsx_rows(
    zf: zipfile.ZipFile, sheet_name: str, shared: list[str]
) -> list[list[str]]:
    root = ET.fromstring(zf.read(sheet_name))
    rows: list[list[str]] = []
    for row in root.iter(f"{OOXML_NS}row"):
        values: list[str] = []
        for cell in row.findall(f"{OOXML_NS}c"):
            ref = cell.attrib.get("r", "")
            col_idx = _xlsx_col_index(ref)
            while col_idx is not None and len(values) < col_idx:
                values.append("")
            value = cell.find(f"{OOXML_NS}v")
            inline = cell.find(f"{OOXML_NS}is/{OOXML_NS}t")
            if value is None or value.text is None:
                values.append(inline.text if inline is not None and inline.text else "")
                continue
            raw = value.text
            if cell.attrib.get("t") == "s":
                idx = int(raw)
                values.append(shared[idx] if idx < len(shared) else "")
            else:
                values.append(raw)
        rows.append(values)
    return rows


def _xlsx_col_index(ref: str) -> int | None:
    letters = "".join(ch for ch in ref if ch.isalpha())
    if not letters:
        return None
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch.upper()) - ord("A") + 1)
    return idx - 1


def write_markdown(records: list[SheetInventory], path: Path, root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_count = len({r.file_path for r in records})
    warn_records = [r for r in records if r.warnings]

    lines: list[str] = [
        "# BOOM Excel Metadata Corpus 0.1A Inventory",
        "",
        f"- 生成时间：{generated}",
        f"- 扫描根目录：`{root.as_posix()}`",
        f"- Excel 文件数：**{file_count}**",
        f"- Sheet 数：**{len(records)}**",
        f"- 含 warning 的 sheet：**{len(warn_records)}**",
        "",
        "## Summary",
        "",
        "| 指标 | 值 |",
        "| --- | --- |",
        f"| files | {file_count} |",
        f"| sheets | {len(records)} |",
        f"| total_rows | {sum(r.row_count for r in records)} |",
        f"| warning_sheets | {len(warn_records)} |",
        "",
    ]

    if warn_records:
        lines.extend(["## Warnings", ""])
        for record in warn_records:
            joined = "; ".join(record.warnings)
            lines.append(f"- `{record.file_path}` / `{record.sheet_name}`: {joined}")
        lines.append("")

    lines.extend(["## Inventory", ""])
    current_file = ""
    for record in records:
        if record.file_path != current_file:
            current_file = record.file_path
            lines.extend([f"### {record.file_name}", "", f"- path: `{record.file_path}`", ""])

        lines.extend(
            [
                f"#### Sheet: {record.sheet_name}",
                "",
                f"- rows: **{record.row_count}** | columns: **{record.column_count}**",
                f"- headers: `{json.dumps(record.headers, ensure_ascii=False)}`",
            ]
        )

        for role in ROLE_ORDER:
            cols = record.guessed_columns.get(role, [])
            if cols:
                lines.append(f"- {role}: `{json.dumps(cols, ensure_ascii=False)}`")

        if record.sample_rows:
            lines.append(f"- sample_rows: `{json.dumps(record.sample_rows, ensure_ascii=False)}`")

        if record.warnings:
            lines.append(f"- warnings: `{json.dumps(record.warnings, ensure_ascii=False)}`")

        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_csv(records: list[SheetInventory], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "file_path",
        "file_name",
        "sheet_name",
        "row_count",
        "column_count",
        "header_list",
        *ROLE_ORDER,
        "sample_rows",
        "warnings",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = {
                "file_path": record.file_path,
                "file_name": record.file_name,
                "sheet_name": record.sheet_name,
                "row_count": record.row_count,
                "column_count": record.column_count,
                "header_list": json.dumps(record.headers, ensure_ascii=False),
                "sample_rows": json.dumps(record.sample_rows, ensure_ascii=False),
                "warnings": json.dumps(record.warnings, ensure_ascii=False),
            }
            for role in ROLE_ORDER:
                row[role] = json.dumps(record.guessed_columns.get(role, []), ensure_ascii=False)
            writer.writerow(row)


if __name__ == "__main__":
    raise SystemExit(main())
