#!/usr/bin/env python3
"""Mine de-duplicated token/phrase evidence from the BOOM metadata corpus."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fxengine.canonical_db import CANONICAL_COLUMNS, DEFAULT_CANONICAL_PATH  # noqa: E402


DEFAULT_DB = ROOT / "data" / "boomone" / "boomone_records.sqlite"
DEFAULT_OUTPUT_DIR = ROOT / "exports" / "boomone_mining"
DEFAULT_QUALITY_REPORT = ROOT / "reports" / "boomone_mining_quality_report.md"
MINING_FIELDS = ("fx_name", "description", "keywords", "filename")
MAPPING_FIELDS = (
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
TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*")
FILE_EXTENSION_TOKENS = {"wav", "wave", "mp3", "aif", "aiff", "flac"}
TAKE_INDEX_RE = re.compile(r"^(?:take|tk|index|idx)[-_]?\d*$")
SAMPLE_RATE_RE = re.compile(r"^\d+(?:\.\d+)?k(?:hz)?$")
BIT_DEPTH_RE = re.compile(r"^\d+(?:bit|bits)$")
CHANNEL_FORMAT_TOKENS = {"mono", "stereo", "dualmono", "ms", "ab"}
VERSION_RENDER_RE = re.compile(r"^(?:v|ver|version)[-_]?\d+$")
VERSION_RENDER_TOKENS = {"edit", "final", "master", "premix", "render"}
SINGLE_LETTER_WHITELIST = frozenset()
VENDOR_MARKER_TOKENS = {"b00m", "boomlibrary"}
ALPHANUMERIC_CODE_RE = re.compile(r"^(?=.*[a-z])(?=.*\d)[a-z0-9-]+$")
MIC_MODEL_RE = re.compile(
    r"^(?:mkh|mk|co|ntg|sm|km|md|at|dpa|ccm|cmc|rode|schoeps|neumann|sennheiser)"
    r"[-_]?\d+[a-z0-9-]*$"
)
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
    "audio",
    "file",
    "files",
    "recorded",
    "recording",
    "mic",
    "microphone",
    "position",
    "positioned",
    "sample",
    "samples",
    "sfx",
    "sound",
    "sounds",
}
ACTION_TERMS = {
    "bang",
    "blast",
    "break",
    "clink",
    "crack",
    "crash",
    "creak",
    "drop",
    "flap",
    "friction",
    "hit",
    "impact",
    "knock",
    "rattle",
    "ring",
    "roll",
    "scrape",
    "scratch",
    "slam",
    "snap",
    "splash",
    "squeak",
    "tap",
    "whoosh",
}
HIGH_AMBIGUITY_ACTIONS = {"bang", "break", "crack", "drop", "hit", "ring", "roll"}
OBJECT_TERMS = {
    "body",
    "car",
    "chain",
    "cloth",
    "cup",
    "door",
    "engine",
    "fire",
    "glass",
    "gravel",
    "gun",
    "metal",
    "stone",
    "vehicle",
    "water",
    "weapon",
    "wood",
}
EXAMPLE_FIELDS = (
    "record_id",
    "library",
    "filename",
    "fx_name",
    "description",
    "cat_id",
    "category",
    "subcategory",
    "microphone",
    "source_file",
)


@dataclass(frozen=True)
class MiningSummary:
    record_count: int
    token_count: int
    phrase_count: int
    output_dir: str
    filtered_token_count: int
    filtered_tokens: tuple[str, ...]
    filtered_reasons: dict[str, int]
    candidate_count: int = 0
    candidate_path: str | None = None
    input_files: tuple[str, ...] = ()
    field_mapping_summary: dict[str, int] = field(default_factory=dict)
    canonical_tokens_sha256_before: str = ""
    canonical_tokens_sha256_after: str = ""
    canonical_tokens_changed: bool = False


def mine_corpus(
    db_path: Path = DEFAULT_DB,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    limit: int = 500,
    min_count: int = 1,
    examples_per_item: int = 3,
    candidate_path: Path | None = None,
    candidate_min_count: int = 2,
    quality_report_path: Path | None = None,
) -> MiningSummary:
    """Write evidence exports and optionally inert review-only candidates."""
    db_path = Path(db_path)
    output_dir = Path(output_dir)
    if not db_path.is_file():
        raise FileNotFoundError(f"BOOM corpus database not found: {db_path}")
    if limit < 1 or min_count < 1 or examples_per_item < 1 or candidate_min_count < 1:
        raise ValueError(
            "limit, min_count, examples_per_item, and candidate_min_count must be positive"
        )

    canonical_before = _sha256(DEFAULT_CANONICAL_PATH)
    records = _read_records(db_path)
    token_records: Counter[str] = Counter()
    token_field_hits: Counter[str] = Counter()
    phrase_records: Counter[str] = Counter()
    phrase_field_hits: Counter[str] = Counter()
    filtered_tokens: Counter[str] = Counter()
    filtered_reasons: Counter[str] = Counter()
    filtered_details: Counter[tuple[str, str]] = Counter()
    token_examples: dict[str, list[dict[str, object]]] = defaultdict(list)
    phrase_examples: dict[str, list[dict[str, object]]] = defaultdict(list)

    for record in records:
        record_tokens: set[str] = set()
        record_phrases: set[str] = set()
        category_codes = _record_category_codes(record)
        for field_name in MINING_FIELDS:
            field_value = str(record.get(field_name, "") or "")
            tokens, filtered = _partition_tokens(field_value, field_name)
            retained_tokens: list[str] = []
            for token in tokens:
                if (
                    token in category_codes
                    and token not in ACTION_TERMS
                    and token not in OBJECT_TERMS
                ):
                    filtered.append((token, "category_code"))
                else:
                    retained_tokens.append(token)
            tokens = retained_tokens
            for token, reason in filtered:
                filtered_tokens[token] += 1
                filtered_reasons[reason] += 1
                filtered_details[(token, reason)] += 1

            unique_tokens = set(tokens)
            token_field_hits.update(unique_tokens)
            record_tokens.update(unique_tokens)
            for token in sorted(unique_tokens):
                _append_example(
                    token_examples[token],
                    record,
                    field_name,
                    field_value,
                    examples_per_item,
                )

            unique_phrases: set[str] = set()
            for size in (2, 3):
                unique_phrases.update(
                    " ".join(tokens[index : index + size])
                    for index in range(0, len(tokens) - size + 1)
                )
            phrase_field_hits.update(unique_phrases)
            record_phrases.update(unique_phrases)
            for phrase in sorted(unique_phrases):
                _append_example(
                    phrase_examples[phrase],
                    record,
                    field_name,
                    field_value,
                    examples_per_item,
                )

        token_records.update(record_tokens)
        phrase_records.update(record_phrases)

    top_tokens = _rank_items(token_records, min_count, limit)
    top_phrases = _rank_items(phrase_records, min_count, limit)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_top_tokens(
        output_dir / "top_tokens.csv",
        top_tokens,
        token_field_hits,
        token_examples,
    )
    _write_top_phrases(
        output_dir / "top_phrases.csv",
        top_phrases,
        phrase_field_hits,
        phrase_examples,
    )
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

    candidate_count = 0
    normalized_candidate_path: Path | None = None
    if candidate_path is not None:
        normalized_candidate_path = Path(candidate_path)
        candidate_count = _write_candidates(
            normalized_candidate_path,
            top_tokens,
            top_phrases,
            token_field_hits,
            phrase_field_hits,
            min_count=candidate_min_count,
        )

    canonical_after = _sha256(DEFAULT_CANONICAL_PATH)
    input_files = tuple(
        sorted(
            {
                str(record.get("source_file", "")).split("#", 1)[0]
                for record in records
                if record.get("source_file")
            }
        )
    )
    mapping_summary = {
        field_name: sum(bool(str(record.get(field_name, "") or "").strip()) for record in records)
        for field_name in MAPPING_FIELDS
    }
    summary = MiningSummary(
        record_count=len(records),
        token_count=len(top_tokens),
        phrase_count=len(top_phrases),
        output_dir=str(output_dir),
        filtered_token_count=sum(filtered_tokens.values()),
        filtered_tokens=tuple(sorted(filtered_tokens)),
        filtered_reasons=dict(sorted(filtered_reasons.items())),
        candidate_count=candidate_count,
        candidate_path=(str(normalized_candidate_path) if normalized_candidate_path else None),
        input_files=input_files,
        field_mapping_summary=mapping_summary,
        canonical_tokens_sha256_before=canonical_before,
        canonical_tokens_sha256_after=canonical_after,
        canonical_tokens_changed=canonical_before != canonical_after,
    )
    if quality_report_path is not None:
        _write_quality_report(
            Path(quality_report_path),
            summary,
            top_tokens,
            top_phrases,
            token_field_hits,
            phrase_field_hits,
            filtered_details,
        )
    return summary


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
            SELECT record_id, library, filename, fx_name, description, cat_id,
                   category, subcategory, category_full, vendor_category, keywords,
                   microphone, source_file
            FROM boomone_records
            ORDER BY record_id
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def _tokenize(text: str) -> list[str]:
    tokens, _filtered = _partition_tokens(text)
    return tokens


def _partition_tokens(
    text: str, field_source: str = ""
) -> tuple[list[str], list[tuple[str, str]]]:
    kept: list[str] = []
    filtered: list[tuple[str, str]] = []
    for match in TOKEN_RE.finditer(text):
        original = match.group(0)
        token = original.casefold()
        reason = _filter_reason(token, original, field_source)
        if reason:
            filtered.append((token, reason))
        else:
            kept.append(token)
    return kept, filtered


def _filter_reason(
    token: str, original: str = "", field_source: str = ""
) -> str | None:
    if token.isdigit():
        return "pure_numeric"
    if token in FILE_EXTENSION_TOKENS:
        return "file_extension"
    if TAKE_INDEX_RE.fullmatch(token):
        return "take_or_index"
    if SAMPLE_RATE_RE.fullmatch(token):
        return "sample_rate"
    if BIT_DEPTH_RE.fullmatch(token):
        return "bit_depth"
    if token in CHANNEL_FORMAT_TOKENS:
        return "channel_or_format"
    if VERSION_RENDER_RE.fullmatch(token) or token in VERSION_RENDER_TOKENS:
        return "version_or_render"
    if MIC_MODEL_RE.fullmatch(token):
        return "microphone_model"
    if token in VENDOR_MARKER_TOKENS:
        return "vendor_marker"
    if ALPHANUMERIC_CODE_RE.fullmatch(token):
        return "alphanumeric_code"
    if (
        field_source in {"filename", "keywords"}
        and original.isupper()
        and 2 <= len(original) <= 12
        and token not in ACTION_TERMS
        and token not in OBJECT_TERMS
    ):
        return "uppercase_code"
    if len(token) == 1 and token.isalpha() and token not in SINGLE_LETTER_WHITELIST:
        return "single_letter"
    if token in STOP_WORDS:
        return "stop_or_metadata"
    return None


def _record_category_codes(record: dict[str, object]) -> set[str]:
    normalized = re.sub(
        r"[^a-z0-9]+", "", str(record.get("cat_id", "") or "").casefold()
    )
    return {normalized} if len(normalized) >= 4 else set()


def _rank_items(
    counts: Counter[str], min_count: int, limit: int
) -> list[tuple[str, int]]:
    eligible = [(item, count) for item, count in counts.items() if count >= min_count]
    eligible.sort(key=lambda item: (-item[1], item[0]))
    return eligible[:limit]


def _append_example(
    examples: list[dict[str, object]],
    record: dict[str, object],
    field_source: str,
    field_value: str,
    limit: int,
) -> None:
    if len(examples) >= limit:
        return
    examples.append(
        {
            **record,
            "field_source": field_source,
            "field_value": field_value,
        }
    )


def _write_top_tokens(
    path: Path,
    rows: list[tuple[str, int]],
    field_hit_counts: Counter[str],
    examples: dict[str, list[dict[str, object]]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("token", "record_count", "field_hit_count", "example_count"),
        )
        writer.writeheader()
        writer.writerows(
            {
                "token": token,
                "record_count": record_count,
                "field_hit_count": field_hit_counts[token],
                "example_count": len(examples[token]),
            }
            for token, record_count in rows
        )


def _write_top_phrases(
    path: Path,
    rows: list[tuple[str, int]],
    field_hit_counts: Counter[str],
    examples: dict[str, list[dict[str, object]]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "phrase",
                "record_count",
                "field_hit_count",
                "example_count",
                "n",
            ),
        )
        writer.writeheader()
        writer.writerows(
            {
                "phrase": phrase,
                "record_count": record_count,
                "field_hit_count": field_hit_counts[phrase],
                "example_count": len(examples[phrase]),
                "n": len(phrase.split()),
            }
            for phrase, record_count in rows
        )


def _write_examples(
    path: Path,
    item_field: str,
    ranked_items: list[str],
    examples: dict[str, list[dict[str, object]]],
) -> None:
    fieldnames = (item_field, "example_rank", "field_source", "field_value", *EXAMPLE_FIELDS)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in ranked_items:
            for rank, record in enumerate(examples[item], start=1):
                writer.writerow(
                    {
                        item_field: item,
                        "example_rank": rank,
                        "field_source": record.get("field_source", ""),
                        "field_value": record.get("field_value", ""),
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


def _write_candidates(
    path: Path,
    top_tokens: list[tuple[str, int]],
    top_phrases: list[tuple[str, int]],
    token_field_hits: Counter[str],
    phrase_field_hits: Counter[str],
    *,
    min_count: int,
) -> int:
    """Write conservative review-only action candidates after an explicit request."""
    if path.name != "canonical_token_candidates.csv":
        raise ValueError(
            "BOOM candidates may only be written to canonical_token_candidates.csv"
        )

    candidates: list[dict[str, str | int]] = []
    for token, record_count in top_tokens:
        if record_count < min_count or token not in ACTION_TERMS:
            continue
        candidates.append(
            _candidate_row(
                token,
                record_count,
                token_field_hits[token],
                action=token,
                is_phrase=False,
            )
        )
    for phrase, record_count in top_phrases:
        parts = phrase.split()
        actions = [part for part in parts if part in ACTION_TERMS]
        if (
            record_count < min_count
            or len(parts) not in {2, 3}
            or len(actions) != 1
            or parts[-1] != actions[0]
        ):
            continue
        candidates.append(
            _candidate_row(
                phrase,
                record_count,
                phrase_field_hits[phrase],
                action=actions[0],
                is_phrase=True,
            )
        )

    candidates.sort(key=lambda row: (str(row["raw"]).count(" "), str(row["raw"])))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANONICAL_COLUMNS)
        writer.writeheader()
        writer.writerows(candidates)
    return len(candidates)


def _candidate_row(
    raw: str,
    record_count: int,
    field_hit_count: int,
    *,
    action: str,
    is_phrase: bool,
) -> dict[str, str | int]:
    ambiguity = "high" if action in HIGH_AMBIGUITY_ACTIONS else "medium"
    return {
        "raw": raw,
        "canonical": " ".join(word.capitalize() for word in raw.split()),
        "slot": "action",
        "lang": "en",
        "priority": 0,
        "rule_type": "phrase_low_confidence" if is_phrase else "ambiguous_single",
        "review_status": "review",
        "ambiguity": ambiguity,
        "tags": "boom/action",
        "source": "boom_mined",
        "note": (
            f"record_count={record_count}; field_hit_count={field_hit_count}; "
            "requires human review"
        ),
    }


def _write_quality_report(
    path: Path,
    summary: MiningSummary,
    top_tokens: list[tuple[str, int]],
    top_phrases: list[tuple[str, int]],
    token_field_hits: Counter[str],
    phrase_field_hits: Counter[str],
    filtered_details: Counter[tuple[str, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# BOOMOne Mining Quality Report",
        "",
        f"- input_files: `{len(summary.input_files)}`",
        f"- record_count: `{summary.record_count}`",
        f"- retained_token_count: `{summary.token_count}`",
        f"- retained_phrase_count: `{summary.phrase_count}`",
        f"- filtered_token_occurrences: `{summary.filtered_token_count}`",
        "",
        "## Input files",
        "",
    ]
    lines.extend(f"- `{source}`" for source in summary.input_files)
    if not summary.input_files:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Field mapping summary",
            "",
            "| field | populated_records | coverage |",
            "| --- | ---: | ---: |",
        ]
    )
    for field_name, count in summary.field_mapping_summary.items():
        coverage = count / summary.record_count if summary.record_count else 0.0
        lines.append(f"| {field_name} | {count} | {coverage:.1%} |")

    lines.extend(
        [
            "",
            "## Top tokens",
            "",
            "| token | record_count | field_hit_count |",
            "| --- | ---: | ---: |",
        ]
    )
    for token, record_count in top_tokens[:25]:
        lines.append(f"| {token} | {record_count} | {token_field_hits[token]} |")

    lines.extend(
        [
            "",
            "## Top phrases",
            "",
            "| phrase | record_count | field_hit_count | n |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for phrase, record_count in top_phrases[:25]:
        lines.append(
            f"| {phrase} | {record_count} | {phrase_field_hits[phrase]} | "
            f"{len(phrase.split())} |"
        )

    lines.extend(["", "## Filtered token summary", ""])
    for reason, count in summary.filtered_reasons.items():
        lines.append(f"- `{reason}`: {count}")

    lines.extend(
        [
            "",
            "## Suspected metadata tokens",
            "",
            "| token | reason | filtered_occurrences |",
            "| --- | --- | ---: |",
        ]
    )
    for (token, reason), count in sorted(
        filtered_details.items(), key=lambda item: (-item[1], item[0])
    )[:30]:
        lines.append(f"| {token} | {reason} | {count} |")

    lines.extend(
        [
            "",
            "## Suspected action tokens",
            "",
            "| token | record_count | field_hit_count |",
            "| --- | ---: | ---: |",
        ]
    )
    action_rows = [row for row in top_tokens if row[0] in ACTION_TERMS][:30]
    for token, count in action_rows:
        lines.append(f"| {token} | {count} | {token_field_hits[token]} |")
    if not action_rows:
        lines.append("| — | 0 | 0 |")

    lines.extend(
        [
            "",
            "## Suspected object tokens",
            "",
            "| token | record_count | field_hit_count |",
            "| --- | ---: | ---: |",
        ]
    )
    object_rows = [row for row in top_tokens if row[0] in OBJECT_TERMS][:30]
    for token, count in object_rows:
        lines.append(f"| {token} | {count} | {token_field_hits[token]} |")
    if not object_rows:
        lines.append("| — | 0 | 0 |")

    lines.extend(
        [
            "",
            "## Candidate generation summary",
            "",
            f"- candidate_generation_requested: `{'yes' if summary.candidate_path else 'no'}`",
            f"- candidate_count: `{summary.candidate_count}`",
            f"- candidate_path: `{summary.candidate_path or 'none'}`",
            "- generated policy: `review_status=review`, `source=boom_mined`",
            "- automatic_promote: `no`",
            "",
            "## Quality guard notes",
            "",
            "- `record_count` is distinct-record frequency; repeated fields cannot inflate it.",
            "- `field_hit_count` is distinct `(record, field_source)` frequency.",
            "- `input_files` lists files represented by at least one corpus record.",
            "- Legacy `.xls` input is not supported by the corpus exporter.",
            "- This report contains aggregates only; example descriptions stay in local exports.",
            "",
            "## Canonical token guard",
            "",
            f"- canonical_tokens_sha256_before: `{summary.canonical_tokens_sha256_before}`",
            f"- canonical_tokens_sha256_after: `{summary.canonical_tokens_sha256_after}`",
            f"- canonical_tokens_changed: `{'yes' if summary.canonical_tokens_changed else 'no'}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--min-count", type=int, default=1)
    parser.add_argument("--examples", type=int, default=3)
    parser.add_argument(
        "--candidates",
        type=Path,
        help=(
            "Explicitly write inert review rows; filename must be "
            "canonical_token_candidates.csv"
        ),
    )
    parser.add_argument(
        "--candidate-min-count",
        type=int,
        default=2,
        help="Minimum distinct record_count for candidate generation",
    )
    parser.add_argument("--quality-report", type=Path)
    args = parser.parse_args(argv)
    try:
        summary = mine_corpus(
            args.db,
            args.output_dir,
            limit=args.limit,
            min_count=args.min_count,
            examples_per_item=args.examples,
            candidate_path=args.candidates,
            candidate_min_count=args.candidate_min_count,
            quality_report_path=args.quality_report,
        )
    except (FileNotFoundError, ValueError, sqlite3.DatabaseError) as exc:
        parser.error(str(exc))
    print(
        f"records={summary.record_count} tokens={summary.token_count} "
        f"phrases={summary.phrase_count} filtered={summary.filtered_token_count} "
        f"candidates={summary.candidate_count} "
        f"canonical_changed={str(summary.canonical_tokens_changed).lower()} "
        f"output={summary.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
