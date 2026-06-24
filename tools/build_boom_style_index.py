#!/usr/bin/env python3
"""Build a local Boom/Soundminer-style English FX-name frequency index."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from glossary.boom_style import DEFAULT_BOOM_INDEX

DEFAULT_INPUT = ROOT / "docs" / "训练数据 metada"
TEXT_EXTS = {".txt", ".md"}
TABLE_EXTS = {".csv", ".tsv"}
JSON_EXTS = {".json", ".jsonl"}
XLSX_EXTS = {".xlsx"}
SUPPORTED_EXTS = TEXT_EXTS | TABLE_EXTS | JSON_EXTS | XLSX_EXTS
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
FIELD_HINTS = (
    "filename",
    "file",
    "description",
    "desc",
    "category",
    "subcategory",
    "keywords",
    "keyword",
    "title",
    "name",
    "metadata",
)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-]*")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="metadata input directory")
    parser.add_argument("--output", default=str(DEFAULT_BOOM_INDEX), help="sqlite index path")
    args = parser.parse_args()

    input_dir = _resolve_input_dir(Path(args.input))
    output_path = Path(args.output)

    token_counts: Counter[str] = Counter()
    filename_token_counts: Counter[str] = Counter()
    phrase_counts: Counter[str] = Counter()
    filename_phrase_counts: Counter[str] = Counter()

    files_read = 0
    english_lines = 0
    for path in _iter_files(input_dir):
        files_read += 1
        for text, is_filename_like in _read_metadata_texts(path):
            tokens = _extract_tokens(text)
            if not tokens:
                continue
            english_lines += 1
            token_counts.update(tokens)
            if is_filename_like:
                filename_token_counts.update(tokens)
            for phrase in _extract_phrases(tokens):
                phrase_counts[phrase] += 1
                if is_filename_like:
                    filename_phrase_counts[phrase] += 1

    _write_index(
        output_path,
        token_counts,
        filename_token_counts,
        phrase_counts,
        filename_phrase_counts,
        files_read,
        english_lines,
    )

    print(f"Input dir: {input_dir}")
    print(f"Read files: {files_read}")
    print(f"English lines: {english_lines}")
    print("Top tokens:", _format_top(token_counts))
    print("Top phrases:", _format_top(phrase_counts))
    print(f"Index path: {output_path}")
    return 0


def _resolve_input_dir(path: Path) -> Path:
    if path.is_dir():
        return path
    if path.name.endswith(" metada"):
        fallback = path.with_name(path.name[: -len(" metada")])
        if fallback.is_dir():
            return fallback
    raise FileNotFoundError(f"metadata input directory not found: {path}")


def _iter_files(input_dir: Path) -> Iterable[Path]:
    for path in sorted(input_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS:
            yield path


def _read_metadata_texts(path: Path) -> Iterable[tuple[str, bool]]:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTS:
        yield from _read_text_lines(path)
    elif suffix in TABLE_EXTS:
        yield from _read_delimited(path)
    elif suffix == ".jsonl":
        yield from _read_jsonl(path)
    elif suffix == ".json":
        yield from _read_json(path)
    elif suffix == ".xlsx":
        yield from _read_xlsx(path)


def _read_text_lines(path: Path) -> Iterable[tuple[str, bool]]:
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip():
            yield line, False


def _read_delimited(path: Path) -> Iterable[tuple[str, bool]]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    with path.open(encoding="utf-8-sig", errors="ignore", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample) if sample.strip() else csv.excel
        except csv.Error:
            dialect = csv.excel_tab if delimiter == "\t" else csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        if reader.fieldnames:
            fields = _select_fields(reader.fieldnames)
            for row in reader:
                for field in fields:
                    value = (row.get(field) or "").strip()
                    if value:
                        yield value, _is_filename_field(field)


def _read_jsonl(path: Path) -> Iterable[tuple[str, bool]]:
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            yield from _collect_json_texts(json.loads(line))
        except json.JSONDecodeError:
            continue


def _read_json(path: Path) -> Iterable[tuple[str, bool]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return
    yield from _collect_json_texts(data)


def _read_xlsx(path: Path) -> Iterable[tuple[str, bool]]:
    with zipfile.ZipFile(path) as zf:
        shared = _read_xlsx_shared_strings(zf)
        sheet_names = [n for n in zf.namelist() if n.startswith("xl/worksheets/sheet")]
        for sheet_name in sheet_names:
            rows = list(_read_xlsx_rows(zf, sheet_name, shared))
            if not rows:
                continue
            headers = [str(cell).strip() for cell in rows[0]]
            selected = _select_field_indexes(headers)
            data_rows = rows[1:] if selected else rows
            if selected:
                for row in data_rows:
                    for idx, header in selected:
                        if idx < len(row) and str(row[idx]).strip():
                            yield str(row[idx]), _is_filename_field(header)
            else:
                for row in data_rows:
                    for value in row:
                        if str(value).strip():
                            yield str(value), False


def _read_xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    strings: list[str] = []
    for si in root.findall(f"{ns}si"):
        pieces = [node.text or "" for node in si.iter(f"{ns}t")]
        strings.append("".join(pieces))
    return strings


def _read_xlsx_rows(
    zf: zipfile.ZipFile, sheet_name: str, shared: list[str]
) -> Iterable[list[str]]:
    root = ET.fromstring(zf.read(sheet_name))
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    for row in root.iter(f"{ns}row"):
        values: list[str] = []
        for cell in row.findall(f"{ns}c"):
            ref = cell.attrib.get("r", "")
            col_idx = _xlsx_col_index(ref)
            while col_idx is not None and len(values) < col_idx:
                values.append("")
            value = cell.find(f"{ns}v")
            inline = cell.find(f"{ns}is/{ns}t")
            if value is None or value.text is None:
                values.append(inline.text if inline is not None and inline.text else "")
                continue
            raw = value.text
            if cell.attrib.get("t") == "s":
                idx = int(raw)
                values.append(shared[idx] if idx < len(shared) else "")
            else:
                values.append(raw)
        yield values


def _xlsx_col_index(ref: str) -> int | None:
    letters = "".join(ch for ch in ref if ch.isalpha())
    if not letters:
        return None
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch.upper()) - ord("A") + 1)
    return idx - 1


def _collect_json_texts(data: object, key: str = "") -> Iterable[tuple[str, bool]]:
    if isinstance(data, dict):
        for k, v in data.items():
            yield from _collect_json_texts(v, str(k))
    elif isinstance(data, list):
        for item in data:
            yield from _collect_json_texts(item, key)
    elif isinstance(data, str) and _field_is_relevant(key):
        yield data, _is_filename_field(key)


def _select_fields(fieldnames: list[str]) -> list[str]:
    selected = [name for name in fieldnames if _field_is_relevant(name)]
    return selected or fieldnames


def _select_field_indexes(headers: list[str]) -> list[tuple[int, str]]:
    return [(idx, header) for idx, header in enumerate(headers) if _field_is_relevant(header)]


def _field_is_relevant(name: str) -> bool:
    normalized = name.strip().lower().replace(" ", "_")
    return any(hint in normalized for hint in FIELD_HINTS)


def _is_filename_field(name: str) -> bool:
    normalized = name.strip().lower()
    return "filename" in normalized or normalized in {"file", "name", "title"}


def _extract_tokens(text: str) -> list[str]:
    tokens = [_normalize_token(w) for w in WORD_RE.findall(text)]
    return [t for t in tokens if t and not _is_noise_token(t)]


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


def _write_index(
    output_path: Path,
    token_counts: Counter[str],
    filename_token_counts: Counter[str],
    phrase_counts: Counter[str],
    filename_phrase_counts: Counter[str],
    files_read: int,
    english_lines: int,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output_path) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS tokens;
            DROP TABLE IF EXISTS phrases;
            DROP TABLE IF EXISTS stats;
            CREATE TABLE tokens (
                token TEXT PRIMARY KEY,
                freq INTEGER NOT NULL,
                filename_freq INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE phrases (
                phrase TEXT PRIMARY KEY,
                n INTEGER NOT NULL,
                freq INTEGER NOT NULL,
                filename_freq INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE stats (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
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
        conn.executemany(
            "INSERT INTO stats(key, value) VALUES (?, ?)",
            [("files_read", str(files_read)), ("english_lines", str(english_lines))],
        )
        conn.execute("CREATE INDEX idx_phrases_weight ON phrases(freq, filename_freq)")
        conn.execute("CREATE INDEX idx_phrases_n ON phrases(n)")


def _format_top(counter: Counter[str], limit: int = 12) -> str:
    return ", ".join(f"{term}:{freq}" for term, freq in counter.most_common(limit))


if __name__ == "__main__":
    raise SystemExit(main())
