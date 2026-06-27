#!/usr/bin/env python3
"""Mine deterministic token/phrase frequency exports from the BOOM corpus."""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "boomone" / "boomone_records.sqlite"
DEFAULT_OUTPUT_DIR = ROOT / "exports" / "boomone_mining"
TEXT_FIELDS = ("fx_name", "description", "keywords")
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:['-][A-Za-z0-9]+)*")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}
EXAMPLE_FIELDS = (
    "record_id",
    "filename",
    "fx_name",
    "description",
    "cat_id",
    "category",
    "subcategory",
    "source_file",
)


@dataclass(frozen=True)
class MiningSummary:
    record_count: int
    token_count: int
    phrase_count: int
    output_dir: str


def mine_corpus(
    db_path: Path = DEFAULT_DB,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    limit: int = 500,
    min_count: int = 1,
    examples_per_item: int = 3,
) -> MiningSummary:
    """Write frequency/evidence exports; never writes candidates or canonical data."""
    db_path = Path(db_path)
    output_dir = Path(output_dir)
    if not db_path.is_file():
        raise FileNotFoundError(f"BOOM corpus database not found: {db_path}")
    if limit < 1 or min_count < 1 or examples_per_item < 1:
        raise ValueError("limit, min_count, and examples_per_item must be positive")

    records = _read_records(db_path)
    token_occurrences: Counter[str] = Counter()
    token_documents: Counter[str] = Counter()
    phrase_occurrences: Counter[str] = Counter()
    phrase_documents: Counter[str] = Counter()
    token_examples: dict[str, list[dict[str, object]]] = defaultdict(list)
    phrase_examples: dict[str, list[dict[str, object]]] = defaultdict(list)

    for record in records:
        record_tokens: set[str] = set()
        record_phrases: set[str] = set()
        for field_name in TEXT_FIELDS:
            tokens = _tokenize(str(record[field_name]))
            token_occurrences.update(tokens)
            record_tokens.update(tokens)
            for size in (2, 3):
                phrases = [
                    " ".join(tokens[index : index + size])
                    for index in range(0, len(tokens) - size + 1)
                ]
                phrase_occurrences.update(phrases)
                record_phrases.update(phrases)
        token_documents.update(record_tokens)
        phrase_documents.update(record_phrases)
        for token in record_tokens:
            if len(token_examples[token]) < examples_per_item:
                token_examples[token].append(record)
        for phrase in record_phrases:
            if len(phrase_examples[phrase]) < examples_per_item:
                phrase_examples[phrase].append(record)

    top_tokens = _rank_items(token_occurrences, min_count, limit)
    top_phrases = _rank_items(phrase_occurrences, min_count, limit)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_top_tokens(output_dir / "top_tokens.csv", top_tokens, token_documents)
    _write_top_phrases(output_dir / "top_phrases.csv", top_phrases, phrase_documents)
    _write_examples(
        output_dir / "token_examples.csv",
        "token",
        [item for item, _count in top_tokens],
        token_examples,
    )
    _write_examples(
        output_dir / "phrase_examples.csv",
        "phrase",
        [item for item, _count in top_phrases],
        phrase_examples,
    )
    _write_description_examples(output_dir / "description_examples.csv", records)
    return MiningSummary(
        record_count=len(records),
        token_count=len(top_tokens),
        phrase_count=len(top_phrases),
        output_dir=str(output_dir),
    )


def _read_records(db_path: Path) -> list[dict[str, object]]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='boomone_records'"
        ).fetchone()
        if table is None:
            raise ValueError("boomone_records table is missing")
        rows = connection.execute(
            """
            SELECT record_id, filename, fx_name, description, cat_id, category,
                   subcategory, keywords, source_file
            FROM boomone_records
            ORDER BY record_id
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def _tokenize(text: str) -> list[str]:
    return [
        match.group(0).casefold()
        for match in TOKEN_RE.finditer(text)
        if match.group(0).casefold() not in STOP_WORDS
    ]


def _rank_items(
    counts: Counter[str], min_count: int, limit: int
) -> list[tuple[str, int]]:
    eligible = [(item, count) for item, count in counts.items() if count >= min_count]
    eligible.sort(key=lambda item: (-item[1], item[0]))
    return eligible[:limit]


def _write_top_tokens(
    path: Path,
    rows: list[tuple[str, int]],
    document_counts: Counter[str],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=("token", "count", "record_count")
        )
        writer.writeheader()
        writer.writerows(
            {
                "token": token,
                "count": count,
                "record_count": document_counts[token],
            }
            for token, count in rows
        )


def _write_top_phrases(
    path: Path,
    rows: list[tuple[str, int]],
    document_counts: Counter[str],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=("phrase", "count", "record_count", "n")
        )
        writer.writeheader()
        writer.writerows(
            {
                "phrase": phrase,
                "count": count,
                "record_count": document_counts[phrase],
                "n": len(phrase.split()),
            }
            for phrase, count in rows
        )


def _write_examples(
    path: Path,
    item_field: str,
    ranked_items: list[str],
    examples: dict[str, list[dict[str, object]]],
) -> None:
    fieldnames = (item_field, "example_rank", *EXAMPLE_FIELDS)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in ranked_items:
            for rank, record in enumerate(examples[item], start=1):
                writer.writerow(
                    {
                        item_field: item,
                        "example_rank": rank,
                        **{field: record.get(field, "") for field in EXAMPLE_FIELDS},
                    }
                )


def _write_description_examples(
    path: Path, records: list[dict[str, object]]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXAMPLE_FIELDS)
        writer.writeheader()
        writer.writerows(
            {field: record.get(field, "") for field in EXAMPLE_FIELDS}
            for record in records
            if str(record.get("description", "")).strip()
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--min-count", type=int, default=1)
    parser.add_argument("--examples", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        summary = mine_corpus(
            args.db,
            args.output_dir,
            limit=args.limit,
            min_count=args.min_count,
            examples_per_item=args.examples,
        )
    except (FileNotFoundError, ValueError, sqlite3.DatabaseError) as exc:
        parser.error(str(exc))
    print(
        f"records={summary.record_count} tokens={summary.token_count} "
        f"phrases={summary.phrase_count} output={summary.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
