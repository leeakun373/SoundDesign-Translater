#!/usr/bin/env python3
"""Build a deterministic, reviewable BOOM candidate evidence pack."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fxengine.canonical_db import CANONICAL_COLUMNS, DEFAULT_CANONICAL_PATH  # noqa: E402
from tools.mine_boomone_tokens import MINING_FIELDS, _partition_tokens  # noqa: E402


DEFAULT_MINING_DIR = ROOT / "exports" / "boomone_mining"
DEFAULT_DB = ROOT / "data" / "boomone" / "boomone_records.sqlite"
DEFAULT_OUTPUT_DIR = ROOT / "exports" / "boomone_candidates"
DEFAULT_REPORT = ROOT / "reports" / "boomone_candidate_evidence_report.md"
DEFAULT_QA_REPORT = ROOT / "reports" / "boom_evidence_qa_report.md"

EVIDENCE_COLUMNS = (
    "raw",
    "canonical_guess",
    "kind",
    "slot_guess",
    "record_count",
    "field_hit_count",
    "example_count",
    "score",
    "decision",
    "reason",
    "source_fields",
    "example_1",
    "example_2",
    "example_3",
    "catid_samples",
    "category_samples",
    "source_files",
    "fx_name_hits",
    "description_hits",
    "keywords_hits",
    "filename_hits",
    "field_quality",
    "example_quality",
    "category_alignment",
    "existing_canonical_status",
    "approved_for_ai",
    "qa_flags",
)
EXPANDED_EXAMPLE_COLUMNS = (
    "raw",
    "canonical_guess",
    "example_rank",
    "match_field",
    "match_quality",
    "fx_name",
    "description",
    "keywords",
    "filename",
    "cat_id",
    "category",
    "subcategory",
    "source_file",
    "flags",
)
EXPANSION_SEARCH_FIELDS = (
    "fx_name",
    "keywords",
    "description",
    "filename",
    "category",
    "subcategory",
    "cat_id",
)

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
PRIMARY_OBJECT_TERMS = {
    "gun",
    "metal",
    "car",
    "vehicle",
    "wood",
    "door",
    "water",
    "fire",
    "engine",
    "weapon",
    "cloth",
    "chain",
    "stone",
    "body",
    "glass",
}
EXTENDED_OBJECT_TERMS = {
    "cannon",
    "artillery",
    "gravel",
    "mud",
    "leaf",
    "leaves",
    "rope",
    "switch",
    "button",
    "drawer",
    "cabinet",
    "machine",
    "motor",
    "creature",
    "monster",
    "crowd",
    "footstep",
}
MATERIAL_TERMS = {
    "metal",
    "wood",
    "glass",
    "cloth",
    "stone",
    "gravel",
    "water",
    "fire",
    "rubber",
    "plastic",
    "ceramic",
    "leather",
    "dirt",
    "sand",
    "ice",
    "paper",
}
MODIFIER_TERMS = {"short", "long", "fast", "slow", "heavy", "soft", "hard"}
DETAIL_TERMS = {"close", "distant", "dry", "wet", "bright", "dark", "tonal", "low", "high"}
EMERGING_ACTION_TERMS = {"shot"}
PHRASE_ACTION_TERMS = ACTION_TERMS | EMERGING_ACTION_TERMS

EXPLICIT_NOISE_TOKENS = {"cal", "group", "single", "shots", "shooter", "elements"}
EXPLICIT_NOISE_PHRASES = {
    "world war",
    "second world",
    "second world war",
    "war wwii",
    "war wwii weapons",
    "wwii weapons",
    "sanken high",
    "sanken high frequency",
    "frequency response",
    "high frequency",
    "high frequency response",
    "very close",
    "open field",
    "group shots",
    "away cannon",
}
MIC_SPEC_TERMS = {
    "frequency",
    "response",
    "sanken",
    "schoeps",
    "sennheiser",
    "neumann",
    "microphone",
    "lavalier",
    "ortf",
}
LIBRARY_CONTEXT_TERMS = {"wwii", "war"}
UNNATURAL_LEADS = {"away", "near", "far", "inside", "outside"}
GENERIC_COUNT_TERMS = {"single", "group", "multiple", "shots"}
HIGH_AMBIGUITY_ACTIONS = {"bang", "break", "crack", "drop", "hit", "ring", "roll"}
HIGH_RISK_TOKENS = {
    "hit",
    "shot",
    "ring",
    "drop",
    "break",
    "crack",
    "roll",
    "fire",
    "gun",
    "body",
    "hard",
    "soft",
    "low",
    "high",
    "single",
    "short",
    "long",
    "movement",
    "tonal",
}
CATEGORY_ALIGNMENT_TERMS = {
    "hit": {"hit", "impact", "fight", "punch", "weapon"},
    "shot": {"shot", "gun", "weapon", "bullet", "firearm", "cannon", "artillery"},
    "ring": {"ring", "bell", "metal", "percussion"},
    "drop": {"drop", "impact", "foley", "chain", "metal"},
    "break": {"break", "destruction", "glass", "wood", "impact"},
    "crack": {"crack", "impact", "explosion", "wood"},
    "roll": {"roll", "wheel", "vehicle", "foley"},
    "fire": {"fire", "flame", "burn", "gun", "weapon"},
    "gun": {"gun", "weapon", "firearm", "rifle", "pistol", "cannon"},
    "body": {"body", "foley", "fight", "human"},
}
EXAMPLE_SOURCE_PRIORITY = {
    "fx_name": 0,
    "keywords": 1,
    "description": 2,
    "filename": 3,
}


@dataclass(frozen=True)
class EvidenceSummary:
    token_count: int
    phrase_count: int
    action_candidate_count: int
    object_candidate_count: int
    material_candidate_count: int
    detail_modifier_candidate_count: int
    phrase_candidate_count: int
    rejected_noise_count: int
    output_dir: str
    report_path: str
    qa_report_path: str
    total_evidence_count: int
    approved_for_ai_count: int
    blocked_for_ai_count: int
    written_candidate_count: int
    candidate_path: str | None
    canonical_tokens_sha256_before: str
    canonical_tokens_sha256_after: str
    canonical_tokens_changed: bool
    expanded_examples_path: str = ""
    expanded_evidence_count: int = 0
    approved_for_ai_before_expansion_count: int = 0


@dataclass
class CorpusEvidence:
    field_counts: dict[str, Counter[str]]
    catids: dict[str, Counter[str]]
    categories: dict[str, Counter[str]]
    source_files: dict[str, Counter[str]]
    aligned_records: Counter[str]
    qa_aligned_records: Counter[str]
    categorized_records: Counter[str]


def build_candidate_evidence(
    top_tokens_path: Path = DEFAULT_MINING_DIR / "top_tokens.csv",
    top_phrases_path: Path = DEFAULT_MINING_DIR / "top_phrases.csv",
    token_examples_path: Path = DEFAULT_MINING_DIR / "token_examples.csv",
    phrase_examples_path: Path = DEFAULT_MINING_DIR / "phrase_examples.csv",
    db_path: Path = DEFAULT_DB,
    canonical_path: Path = DEFAULT_CANONICAL_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    report_path: Path = DEFAULT_REPORT,
    qa_report_path: Path | None = None,
    *,
    write_candidates: Path | None = None,
    candidate_threshold: int = 70,
    max_examples_per_candidate: int = 20,
) -> EvidenceSummary:
    """Create evidence CSVs and optionally write inert review-only candidates."""
    paths = tuple(
        Path(path)
        for path in (
            top_tokens_path,
            top_phrases_path,
            token_examples_path,
            phrase_examples_path,
            db_path,
            canonical_path,
        )
    )
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Required input not found: {missing[0]}")
    if not 0 <= candidate_threshold <= 100:
        raise ValueError("candidate_threshold must be between 0 and 100")
    if max_examples_per_candidate < 1:
        raise ValueError("max_examples_per_candidate must be positive")

    canonical_path = Path(canonical_path)
    qa_report_path = (
        Path(qa_report_path)
        if qa_report_path is not None
        else Path(report_path).with_name(DEFAULT_QA_REPORT.name)
    )
    canonical_before = _sha256(canonical_path)
    token_frequency = _read_frequency_rows(Path(top_tokens_path), "token")
    phrase_frequency = _read_frequency_rows(Path(top_phrases_path), "phrase")
    token_examples = _read_example_rows(Path(token_examples_path), "token")
    phrase_examples = _read_example_rows(Path(phrase_examples_path), "phrase")
    all_items = set(token_frequency) | set(phrase_frequency)
    corpus = _scan_corpus(Path(db_path), all_items)
    governed_rows = _read_governed_rows(canonical_path)

    rows: list[dict[str, object]] = []
    for kind, frequencies, examples in (
        ("token", token_frequency, token_examples),
        ("phrase", phrase_frequency, phrase_examples),
    ):
        for raw, frequency in frequencies.items():
            rows.append(
                _build_evidence_row(
                    raw,
                    kind,
                    frequency,
                    examples.get(raw, []),
                    corpus,
                    governed_rows,
                )
            )

    rows.sort(
        key=lambda row: (
            0 if row["kind"] == "token" else 1,
            -int(row["record_count"]),
            str(row["raw"]),
        )
    )
    approved_before_expansion = sum(
        row["approved_for_ai"] == "yes" for row in rows
    )
    rows, expanded_examples = _expand_evidence_rows(
        Path(db_path), rows, max_examples_per_candidate=max_examples_per_candidate
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    expanded_examples_path = output_dir / "expanded_examples.csv"
    _write_expanded_examples_csv(expanded_examples_path, expanded_examples)
    _write_csv(output_dir / "candidate_evidence.csv", rows)

    action_rows = _accepted_rows(rows, slots={"action"}, kinds={"token"})
    object_rows = _accepted_rows(rows, slots={"object"}, kinds={"token"})
    material_rows = _accepted_rows(rows, slots={"material"}, kinds={"token"})
    detail_rows = _accepted_rows(
        rows, slots={"detail", "modifier"}, kinds={"token"}
    )
    phrase_rows = _accepted_rows(rows, slots={"action"}, kinds={"phrase"})
    rejected_rows = [row for row in rows if row["decision"] == "reject"]

    for filename, selected in (
        ("action_candidates.csv", action_rows),
        ("object_candidates.csv", object_rows),
        ("material_candidates.csv", material_rows),
        ("detail_modifier_candidates.csv", detail_rows),
        ("phrase_candidates.csv", phrase_rows),
        ("rejected_noise.csv", rejected_rows),
    ):
        _write_csv(output_dir / filename, selected)

    candidate_count = 0
    candidate_path: Path | None = None
    if write_candidates is not None:
        candidate_path = Path(write_candidates)
        candidate_count = _write_review_candidates(
            candidate_path, rows, candidate_threshold
        )

    canonical_after = _sha256(canonical_path)
    if canonical_after != canonical_before:
        raise RuntimeError("canonical_tokens.csv changed while building evidence")

    summary = EvidenceSummary(
        token_count=len(token_frequency),
        phrase_count=len(phrase_frequency),
        action_candidate_count=len(action_rows),
        object_candidate_count=len(object_rows),
        material_candidate_count=len(material_rows),
        detail_modifier_candidate_count=len(detail_rows),
        phrase_candidate_count=len(phrase_rows),
        rejected_noise_count=len(rejected_rows),
        output_dir=str(output_dir),
        report_path=str(report_path),
        qa_report_path=str(qa_report_path),
        total_evidence_count=len(rows),
        approved_for_ai_count=sum(row["approved_for_ai"] == "yes" for row in rows),
        blocked_for_ai_count=sum(row["approved_for_ai"] == "no" for row in rows),
        written_candidate_count=candidate_count,
        candidate_path=str(candidate_path) if candidate_path else None,
        canonical_tokens_sha256_before=canonical_before,
        canonical_tokens_sha256_after=canonical_after,
        canonical_tokens_changed=False,
        expanded_examples_path=str(expanded_examples_path),
        expanded_evidence_count=len(expanded_examples),
        approved_for_ai_before_expansion_count=approved_before_expansion,
    )
    _write_report(Path(report_path), summary, rows)
    _write_qa_report(Path(qa_report_path), summary, rows)
    return summary


def _read_frequency_rows(path: Path, item_field: str) -> dict[str, dict[str, int]]:
    rows: dict[str, dict[str, int]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {item_field, "record_count", "field_hit_count", "example_count"}
        if not reader.fieldnames or not required <= set(reader.fieldnames):
            raise ValueError(f"{path} is missing required columns: {sorted(required)}")
        for row in reader:
            raw = (row.get(item_field) or "").strip().casefold()
            if not raw:
                continue
            rows[raw] = {
                "record_count": _to_nonnegative_int(row.get("record_count"), path),
                "field_hit_count": _to_nonnegative_int(
                    row.get("field_hit_count"), path
                ),
                "example_count": _to_nonnegative_int(row.get("example_count"), path),
            }
    return rows


def _read_example_rows(path: Path, item_field: str) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or item_field not in reader.fieldnames:
            raise ValueError(f"{path} is missing required column: {item_field}")
        for row in reader:
            raw = (row.get(item_field) or "").strip().casefold()
            if raw:
                grouped[raw].append({key: value or "" for key, value in row.items()})
    for rows in grouped.values():
        rows.sort(key=lambda row: _safe_int(row.get("example_rank"), 9999))
    return grouped


def _scan_corpus(db_path: Path, wanted_items: set[str]) -> CorpusEvidence:
    field_counts: dict[str, Counter[str]] = defaultdict(Counter)
    catids: dict[str, Counter[str]] = defaultdict(Counter)
    categories: dict[str, Counter[str]] = defaultdict(Counter)
    source_files: dict[str, Counter[str]] = defaultdict(Counter)
    aligned_records: Counter[str] = Counter()
    qa_aligned_records: Counter[str] = Counter()
    categorized_records: Counter[str] = Counter()

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='boomone_records'"
        ).fetchone()
        if exists is None:
            raise ValueError("boomone_records table is missing")
        records = connection.execute(
            """
            SELECT record_id, filename, fx_name, description, keywords, cat_id,
                   category, subcategory, source_file
            FROM boomone_records
            ORDER BY record_id
            """
        )
        for record in records:
            record_items: set[str] = set()
            for field_name in MINING_FIELDS:
                tokens, _filtered = _partition_tokens(
                    str(record[field_name] or ""), field_name
                )
                token_matches = set(tokens) & wanted_items
                phrase_matches: set[str] = set()
                for size in (2, 3):
                    phrase_matches.update(
                        " ".join(tokens[index : index + size])
                        for index in range(0, len(tokens) - size + 1)
                    )
                matches = token_matches | (phrase_matches & wanted_items)
                for raw in matches:
                    field_counts[raw][field_name] += 1
                record_items.update(matches)

            category = str(record["category"] or "").strip()
            subcategory = str(record["subcategory"] or "").strip()
            category_sample = "/".join(
                value for value in (category, subcategory) if value
            )
            category_terms = _normalized_words(f"{category} {subcategory}")
            for raw in record_items:
                cat_id = str(record["cat_id"] or "").strip()
                source_file = str(record["source_file"] or "").strip()
                if cat_id:
                    catids[raw][cat_id] += 1
                if category_sample:
                    categories[raw][category_sample] += 1
                if category_sample or cat_id:
                    categorized_records[raw] += 1
                if source_file:
                    source_files[raw][source_file] += 1
                if _normalized_words(raw) & category_terms:
                    aligned_records[raw] += 1
                if _record_category_aligned(raw, category, subcategory, cat_id):
                    qa_aligned_records[raw] += 1
    finally:
        connection.close()
    return CorpusEvidence(
        field_counts=dict(field_counts),
        catids=dict(catids),
        categories=dict(categories),
        source_files=dict(source_files),
        aligned_records=aligned_records,
        qa_aligned_records=qa_aligned_records,
        categorized_records=categorized_records,
    )


def expand_examples_for_candidate(
    connection: sqlite3.Connection,
    raw: str,
    canonical_guess: str,
    *,
    max_examples: int = 20,
) -> list[dict[str, str]]:
    """Return ranked, field-aware SQLite evidence for one mined candidate."""
    if max_examples < 1:
        raise ValueError("max_examples must be positive")
    raw = raw.strip().casefold()
    if not raw:
        return []
    escaped = raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    query = f"%{escaped}%"
    records = connection.execute(
        """
        SELECT record_id, filename, fx_name, description, keywords, cat_id,
               category, subcategory, source_file
        FROM boomone_records
        WHERE fx_name LIKE ? ESCAPE '\\' COLLATE NOCASE
           OR keywords LIKE ? ESCAPE '\\' COLLATE NOCASE
           OR description LIKE ? ESCAPE '\\' COLLATE NOCASE
           OR filename LIKE ? ESCAPE '\\' COLLATE NOCASE
           OR category LIKE ? ESCAPE '\\' COLLATE NOCASE
           OR subcategory LIKE ? ESCAPE '\\' COLLATE NOCASE
           OR cat_id LIKE ? ESCAPE '\\' COLLATE NOCASE
        ORDER BY record_id
        """,
        [query] * len(EXPANSION_SEARCH_FIELDS),
    ).fetchall()
    examples: list[dict[str, str]] = []
    for record in records:
        match_field = _best_expanded_match_field(raw, record)
        if match_field:
            examples.append(
                _expanded_example_row(raw, canonical_guess, record, match_field)
            )
    examples.sort(key=_expanded_example_sort_key)
    selected = examples[:max_examples]
    for index, row in enumerate(selected, start=1):
        row["example_rank"] = str(index)
    return selected


def select_best_examples(
    examples: list[dict[str, str]], *, limit: int = 3
) -> list[dict[str, str]]:
    """Select distinct, high-signal expanded examples for rendered evidence."""
    if limit < 1:
        raise ValueError("limit must be positive")
    unique, _duplicate_count = _unique_expanded_examples(examples)
    return sorted(unique, key=_expanded_example_sort_key)[:limit]


def score_example_quality(examples: list[dict[str, str]]) -> str:
    """Score expanded examples conservatively without invoking an AI service."""
    selected = select_best_examples(examples)
    trusted = sum(
        _example_source_field(row) in {"fx_name", "keywords"} for row in selected
    )
    if not selected or any(_expanded_has_major_noise(row) for row in selected):
        return "low"
    if len(selected) >= 3 and trusted >= (len(selected) + 1) // 2:
        return "high"
    if len(selected) >= 2 and trusted:
        return "medium"
    return "low"


def rescore_candidate_with_expanded_examples(
    row: dict[str, object], examples: list[dict[str, str]]
) -> dict[str, object]:
    """Recalculate evidence QA fields from expanded examples."""
    selected = select_best_examples(examples)
    _unique, duplicate_count = _unique_expanded_examples(examples)
    formatted = [_format_example(example) for example in selected]
    formatted.extend([""] * (3 - len(formatted)))
    field_counts = Counter(example["match_field"] for example in examples)
    raw = str(row["raw"])
    category_alignment = _expanded_category_alignment(raw, examples)
    field_quality = _field_quality(field_counts, selected, category_alignment)
    example_quality = score_example_quality(examples)
    approved_for_ai, qa_flags = _qa_decision(
        raw,
        str(row["kind"]),
        str(row["slot_guess"]),
        str(row["decision"]),
        field_counts,
        selected,
        field_quality,
        example_quality,
        category_alignment,
        str(row["existing_canonical_status"]),
        duplicate_count,
    )
    updated = dict(row)
    updated.update(
        {
            "source_fields": _format_field_counts(field_counts),
            "example_1": formatted[0],
            "example_2": formatted[1],
            "example_3": formatted[2],
            "catid_samples": _expanded_samples(
                example["cat_id"] for example in examples
            ),
            "category_samples": _expanded_samples(
                "/".join(
                    value
                    for value in (example["category"], example["subcategory"])
                    if value
                )
                for example in examples
            ),
            "source_files": _expanded_samples(
                example["source_file"] for example in examples
            ),
            "fx_name_hits": field_counts.get("fx_name", 0),
            "description_hits": field_counts.get("description", 0),
            "keywords_hits": field_counts.get("keywords", 0),
            "filename_hits": field_counts.get("filename", 0),
            "field_quality": field_quality,
            "example_quality": example_quality,
            "category_alignment": category_alignment,
            "approved_for_ai": approved_for_ai,
            "qa_flags": ";".join(qa_flags),
        }
    )
    return {column: updated.get(column, "") for column in EVIDENCE_COLUMNS}


def _expand_evidence_rows(
    db_path: Path,
    rows: list[dict[str, object]],
    *,
    max_examples_per_candidate: int,
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    expanded_rows: list[dict[str, str]] = []
    rescored_rows: list[dict[str, object]] = []
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        _assert_boomone_records_table(connection)
        for row in rows:
            examples = expand_examples_for_candidate(
                connection,
                str(row["raw"]),
                str(row["canonical_guess"]),
                max_examples=max_examples_per_candidate,
            )
            expanded_rows.extend(examples)
            rescored_rows.append(
                rescore_candidate_with_expanded_examples(row, examples)
            )
    finally:
        connection.close()
    return rescored_rows, expanded_rows


def _assert_boomone_records_table(connection: sqlite3.Connection) -> None:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='boomone_records'"
    ).fetchone()
    if exists is None:
        raise ValueError("boomone_records table is missing")


def _expanded_example_row(
    raw: str, canonical_guess: str, record: sqlite3.Row, match_field: str
) -> dict[str, str]:
    row = {
        "raw": raw,
        "canonical_guess": canonical_guess,
        "example_rank": "0",
        "match_field": match_field,
        "match_quality": "low",
        "fx_name": str(record["fx_name"] or ""),
        "description": str(record["description"] or ""),
        "keywords": str(record["keywords"] or ""),
        "filename": str(record["filename"] or ""),
        "cat_id": str(record["cat_id"] or ""),
        "category": str(record["category"] or ""),
        "subcategory": str(record["subcategory"] or ""),
        "source_file": str(record["source_file"] or ""),
        "flags": "",
    }
    flags = _expanded_example_flags(raw, row, match_field)
    row["flags"] = ";".join(flags)
    row["match_quality"] = _expanded_match_quality(
        raw, row, match_field, flags
    )
    return row


def _expanded_example_flags(
    raw: str, row: dict[str, str], match_field: str
) -> list[str]:
    flags: list[str] = []
    if match_field == "description":
        flags.append("description_only")
    if match_field == "filename":
        flags.append("filename_only")
    if not _record_category_aligned(
        raw, row["category"], row["subcategory"], row["cat_id"]
    ):
        flags.append("category_mismatch")
    text = " ".join(
        row[field]
        for field in ("fx_name", "description", "keywords", "filename")
    ).casefold()
    if "shotgun microphone" in text or "shotgun mic" in text:
        flags.append("shotgun_microphone")
    if (
        any(term in text for term in ("tape gun", "glue gun", "tool gun"))
        and not _weapon_category(row)
    ):
        flags.append("tool_gun_context")
    if row["category"].casefold().startswith("ambience") and match_field == "description":
        flags.append("ambience_context")
    if any(term in text for term in ("microphone", "frequency response")):
        flags.append("metadata_context")
    return list(dict.fromkeys(flags))


def _expanded_match_quality(
    raw: str,
    row: dict[str, str],
    match_field: str,
    flags: list[str],
) -> str:
    if _expanded_has_major_noise({"flags": ";".join(flags)}):
        return "low"
    if match_field == "fx_name":
        return "high"
    if match_field == "keywords" and _record_category_aligned(
        raw, row["category"], row["subcategory"], row["cat_id"]
    ):
        return "high"
    if match_field == "description" and "category_mismatch" not in flags:
        return "medium"
    return "low"


def _best_expanded_match_field(raw: str, record: sqlite3.Row) -> str:
    for field in EXPANSION_SEARCH_FIELDS:
        if _contains_candidate(raw, str(record[field] or "")):
            return field
    return ""


def _contains_candidate(raw: str, text: str) -> bool:
    return bool(
        re.search(
            r"(?<![a-z0-9])" + re.escape(raw.casefold()) + r"(?![a-z0-9])",
            text.casefold(),
        )
    )


def _expanded_example_sort_key(
    row: dict[str, str],
) -> tuple[int, int, int, str, str, str]:
    quality = {"high": 0, "medium": 1, "low": 2}
    return (
        EXAMPLE_SOURCE_PRIORITY.get(row.get("match_field", ""), 99),
        quality.get(row.get("match_quality", ""), 99),
        len([flag for flag in row.get("flags", "").split(";") if flag]),
        row.get("source_file", ""),
        row.get("fx_name", ""),
        row.get("filename", ""),
    )


def _unique_expanded_examples(
    examples: list[dict[str, str]],
) -> tuple[list[dict[str, str]], int]:
    unique: list[dict[str, str]] = []
    seen_payloads: set[str] = set()
    seen_fx_names: set[str] = set()
    for row in sorted(examples, key=_expanded_example_sort_key):
        payload = "|".join(
            row.get(field, "").casefold()
            for field in ("fx_name", "filename", "source_file")
        )
        fx_name = row.get("fx_name", "").casefold()
        if payload in seen_payloads or (fx_name and fx_name in seen_fx_names):
            continue
        unique.append(row)
        seen_payloads.add(payload)
        if fx_name:
            seen_fx_names.add(fx_name)
    return unique, len(examples) - len(unique)


def _expanded_has_major_noise(row: dict[str, str]) -> bool:
    flags = {flag for flag in row.get("flags", "").split(";") if flag}
    return bool(
        flags
        & {
            "shotgun_microphone",
            "tool_gun_context",
            "ambience_context",
            "metadata_context",
        }
    )


def _expanded_category_alignment(
    raw: str, examples: list[dict[str, str]]
) -> str:
    categorized = [
        row
        for row in examples
        if row["category"] or row["subcategory"] or row["cat_id"]
    ]
    if not categorized:
        return "unknown"
    aligned = [
        row
        for row in categorized
        if _record_category_aligned(
            raw, row["category"], row["subcategory"], row["cat_id"]
        )
    ]
    ratio = len(aligned) / len(categorized)
    if ratio >= 0.6:
        return "aligned"
    if aligned:
        return "mixed"
    return "weak"


def _expanded_samples(values: Iterable[str], limit: int = 5) -> str:
    return "; ".join(
        value for value, _count in Counter(value for value in values if value).most_common(limit)
    )


def _read_governed_rows(path: Path) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"canonical", "slot", "review_status"}
        if not reader.fieldnames or not required <= set(reader.fieldnames):
            raise ValueError(f"{path} is missing canonical governance columns")
        for row in reader:
            canonical = (row.get("canonical") or "").strip().casefold()
            if canonical:
                grouped[canonical].append(
                    {key: value or "" for key, value in row.items()}
                )
    return dict(grouped)


def _build_evidence_row(
    raw: str,
    kind: str,
    frequency: dict[str, int],
    examples: list[dict[str, str]],
    corpus: CorpusEvidence,
    governed_rows: dict[str, list[dict[str, str]]],
) -> dict[str, object]:
    slot, policy, penalties = _classify(raw, kind)
    record_count = frequency["record_count"]
    field_hit_count = frequency["field_hit_count"]
    field_counts = corpus.field_counts.get(raw, Counter())
    score, components = _score(
        raw,
        kind,
        slot,
        policy,
        penalties,
        record_count,
        field_hit_count,
        field_counts,
        corpus.aligned_records[raw],
    )
    decision = _decision(score, policy)
    canonical_guess = _title_case(raw)
    canonical_matches = governed_rows.get(canonical_guess.casefold(), [])
    canonical_status = _existing_canonical_status(canonical_matches, slot)
    alias_count = len(canonical_matches)
    reason_parts = components or ["no positive scoring signal"]
    if policy:
        reason_parts.append(f"policy={policy}")
    if alias_count:
        reason_parts.append(f"governed_aliases={alias_count}")
    reason = "; ".join(reason_parts)
    selected_examples, duplicate_count = _select_examples(examples)
    formatted_examples = [_format_example(row) for row in selected_examples]
    formatted_examples.extend([""] * (3 - len(formatted_examples)))
    category_alignment = _category_alignment(raw, corpus)
    field_quality = _field_quality(field_counts, selected_examples, category_alignment)
    example_quality = _example_quality(
        selected_examples, len(examples), duplicate_count, category_alignment
    )
    approved_for_ai, qa_flags = _qa_decision(
        raw,
        kind,
        slot,
        decision,
        field_counts,
        selected_examples,
        field_quality,
        example_quality,
        category_alignment,
        canonical_status,
        duplicate_count,
    )
    return {
        "raw": raw,
        "canonical_guess": canonical_guess,
        "kind": kind,
        "slot_guess": slot,
        "record_count": record_count,
        "field_hit_count": field_hit_count,
        "example_count": frequency["example_count"],
        "score": score,
        "decision": decision,
        "reason": reason,
        "source_fields": _format_field_counts(field_counts),
        "example_1": formatted_examples[0],
        "example_2": formatted_examples[1],
        "example_3": formatted_examples[2],
        "catid_samples": _counter_samples(corpus.catids.get(raw, Counter())),
        "category_samples": _counter_samples(
            corpus.categories.get(raw, Counter())
        ),
        "source_files": _counter_samples(
            corpus.source_files.get(raw, Counter())
        ),
        "fx_name_hits": field_counts.get("fx_name", 0),
        "description_hits": field_counts.get("description", 0),
        "keywords_hits": field_counts.get("keywords", 0),
        "filename_hits": field_counts.get("filename", 0),
        "field_quality": field_quality,
        "example_quality": example_quality,
        "category_alignment": category_alignment,
        "existing_canonical_status": canonical_status,
        "approved_for_ai": approved_for_ai,
        "qa_flags": ";".join(qa_flags),
    }


def _select_examples(
    examples: list[dict[str, str]], limit: int = 3
) -> tuple[list[dict[str, str]], int]:
    """Prefer strong evidence fields and return distinct rendered examples."""
    ordered = sorted(
        examples,
        key=lambda row: (
            EXAMPLE_SOURCE_PRIORITY.get(row.get("field_source", ""), 99),
            _safe_int(row.get("example_rank"), 9999),
        ),
    )
    unique: list[dict[str, str]] = []
    seen_payloads: set[str] = set()
    for row in ordered:
        payload = _format_example(row)
        if payload in seen_payloads:
            continue
        seen_payloads.add(payload)
        unique.append(row)

    selected: list[dict[str, str]] = []
    remaining = list(unique)
    while remaining and len(selected) < limit:
        chosen = min(
            remaining,
            key=lambda row: (
                EXAMPLE_SOURCE_PRIORITY.get(row.get("field_source", ""), 99),
                -_example_diversity(row, selected),
                _safe_int(row.get("example_rank"), 9999),
            ),
        )
        selected.append(chosen)
        remaining.remove(chosen)
    return selected, len(examples) - len(unique)


def _example_diversity(
    candidate: dict[str, str], selected: list[dict[str, str]]
) -> int:
    if not selected:
        return 0
    fields = ("source_file", "category", "subcategory", "fx_name")
    return sum(
        all(
            (candidate.get(field) or "").casefold()
            != (existing.get(field) or "").casefold()
            for existing in selected
        )
        for field in fields
    )


def _existing_canonical_status(
    matches: list[dict[str, str]], candidate_slot: str
) -> str:
    if not matches:
        return "existing_unknown"
    statuses = {row.get("review_status", "") for row in matches}
    slots = {row.get("slot", "") for row in matches if row.get("slot")}
    if (
        len(slots) > 1
        or (candidate_slot != "unknown" and slots and candidate_slot not in slots)
        or "reject" in statuses
    ):
        return "existing_conflict"
    if "keep" in statuses:
        return "existing_keep"
    if "review" in statuses:
        return "existing_review"
    return "existing_unknown"


def _record_category_aligned(
    raw: str, category: str, subcategory: str, cat_id: str
) -> bool:
    raw_parts = set(raw.split())
    targets = set(raw_parts)
    for part in raw_parts:
        targets.update(CATEGORY_ALIGNMENT_TERMS.get(part, set()))
    category_text = f"{category} {subcategory} {cat_id}".casefold()
    category_words = _normalized_words(category_text)
    compact = re.sub(r"[^a-z0-9]+", "", category_text)
    return bool(targets & category_words) or any(
        len(target) >= 3 and target in compact for target in targets
    )


def _category_alignment(raw: str, corpus: CorpusEvidence) -> str:
    categorized = corpus.categorized_records[raw]
    aligned = corpus.qa_aligned_records[raw]
    if categorized == 0:
        return "unknown"
    ratio = aligned / categorized
    if ratio >= 0.6:
        return "aligned"
    if aligned:
        return "mixed"
    return "weak"


def _field_quality(
    counts: Counter[str],
    examples: list[dict[str, str]],
    category_alignment: str,
) -> str:
    trusted_hits = counts.get("fx_name", 0) + counts.get("keywords", 0)
    weak_hits = counts.get("description", 0) + counts.get("filename", 0)
    trusted_examples = sum(
        _example_source_field(row) in {"fx_name", "keywords"} for row in examples
    )
    if (
        counts.get("fx_name", 0) > 0
        and trusted_hits >= weak_hits
        and trusted_examples >= max(1, (len(examples) + 1) // 2)
        and category_alignment == "aligned"
    ):
        return "high"
    if trusted_hits > 0:
        return "medium"
    return "low"


def _example_quality(
    examples: list[dict[str, str]],
    original_count: int,
    duplicate_count: int,
    category_alignment: str,
) -> str:
    if not examples:
        return "low"
    trusted = sum(
        _example_source_field(row) in {"fx_name", "keywords"} for row in examples
    )
    if (duplicate_count >= 2 and len(examples) == 1) or trusted == 0:
        return "low"
    if (
        len(examples) >= 2
        and trusted >= (len(examples) + 1) // 2
        and category_alignment == "aligned"
    ):
        return "high"
    if trusted or (original_count >= 2 and len(examples) >= 2):
        return "medium"
    return "low"


def _qa_decision(
    raw: str,
    kind: str,
    slot: str,
    decision: str,
    field_counts: Counter[str],
    examples: list[dict[str, str]],
    field_quality: str,
    example_quality: str,
    category_alignment: str,
    canonical_status: str,
    duplicate_count: int,
) -> tuple[str, list[str]]:
    parts = set(raw.split())
    risk_terms = sorted(parts & HIGH_RISK_TOKENS)
    flags: list[str] = []
    trusted_hits = field_counts.get("fx_name", 0) + field_counts.get("keywords", 0)
    if risk_terms:
        flags.append("ambiguous_token")
    if trusted_hits == 0 and field_counts.get("description", 0):
        flags.append("description_only")
    if trusted_hits == 0 and not field_counts.get("description", 0) and field_counts.get("filename", 0):
        flags.append("filename_only")
    if category_alignment == "weak":
        flags.append("category_mismatch")
    elif category_alignment == "mixed":
        flags.append("category_mixed")
    elif category_alignment == "unknown":
        flags.append("category_unknown")
    if duplicate_count:
        flags.append("duplicate_examples")
    if len(examples) < 2:
        flags.append("insufficient_unique_examples")
    if slot in {"detail", "modifier"}:
        flags.append("detail_modifier")
    if decision == "reject" or slot == "unknown":
        flags.append("rejected_evidence")
    if canonical_status == "existing_conflict":
        flags.append("existing_conflict")

    contextual_blocks: list[str] = []
    if "gun" in parts and any(_is_tool_gun_example(row) for row in examples):
        contextual_blocks.append("tool_gun_context")
    if "shot" in parts and any(_is_shotgun_microphone_example(row) for row in examples):
        contextual_blocks.append("shotgun_microphone")
    if "ring" in parts and any(_is_ambience_description(row) for row in examples):
        contextual_blocks.append("ambience_ring")
    if (
        "hit" in parts
        and field_counts.get("description", 0) > trusted_hits
        and sum(_example_source_field(row) == "description" for row in examples)
        >= max(1, (len(examples) + 1) // 2)
    ):
        contextual_blocks.append("generic_description_hit")
    flags.extend(contextual_blocks)

    approved = (
        decision in {"candidate", "review"}
        and slot not in {"detail", "modifier", "unknown"}
        and field_quality in {"high", "medium"}
        and example_quality in {"high", "medium"}
        and category_alignment in {"aligned", "mixed"}
        and canonical_status != "existing_conflict"
        and not contextual_blocks
    )
    if risk_terms:
        approved = approved and field_quality == "high" and category_alignment == "aligned"
    return ("yes" if approved else "no"), list(dict.fromkeys(flags))


def _is_tool_gun_example(row: dict[str, str]) -> bool:
    text = " ".join(
        row.get(field, "")
        for field in ("field_value", "fx_name", "description", "keywords", "filename")
    ).casefold()
    tool_context = any(phrase in text for phrase in ("tape gun", "glue gun", "tool gun"))
    return tool_context and not _weapon_category(row)


def _is_shotgun_microphone_example(row: dict[str, str]) -> bool:
    text = " ".join(str(value or "") for value in row.values()).casefold()
    return "shotgun microphone" in text or "shotgun mic" in text


def _is_ambience_description(row: dict[str, str]) -> bool:
    category = (row.get("category") or "").casefold()
    return _example_source_field(row) == "description" and category.startswith("ambience")


def _example_source_field(row: dict[str, str]) -> str:
    return row.get("field_source") or row.get("match_field", "")


def _weapon_category(row: dict[str, str]) -> bool:
    text = " ".join(
        row.get(field, "") for field in ("category", "subcategory", "cat_id")
    ).casefold()
    return any(term in text for term in ("gun", "weapon", "rifle", "pistol", "firearm"))


def _classify(raw: str, kind: str) -> tuple[str, str, set[str]]:
    parts = raw.split()
    part_set = set(parts)
    penalties: set[str] = set()
    if raw in EXPLICIT_NOISE_PHRASES or (
        kind == "token" and raw in EXPLICIT_NOISE_TOKENS
    ):
        if part_set & MIC_SPEC_TERMS:
            penalties.add("mic_spec")
        elif part_set & LIBRARY_CONTEXT_TERMS:
            penalties.add("library_context")
        elif raw == "away cannon":
            penalties.add("unnatural_order")
        else:
            penalties.add("metadata_noise")
        return "unknown", "hard_reject", penalties
    if part_set & MIC_SPEC_TERMS:
        return "unknown", "hard_reject", {"mic_spec"}
    if part_set & LIBRARY_CONTEXT_TERMS:
        return "unknown", "hard_reject", {"library_context"}

    if kind == "token":
        if raw in ACTION_TERMS:
            return "action", "known", penalties
        if raw in EMERGING_ACTION_TERMS:
            return "action", "review_only", penalties
        # Material wins for overlapping terms; the reason preserves that decision.
        if raw in MATERIAL_TERMS:
            return "material", "known", penalties
        if raw in PRIMARY_OBJECT_TERMS:
            return "object", "known", penalties
        if raw in EXTENDED_OBJECT_TERMS:
            return "object", "review_only", penalties
        if raw in MODIFIER_TERMS:
            return "modifier", "review_only", penalties
        if raw in DETAIL_TERMS:
            return "detail", "review_only", penalties
        return "unknown", "unknown", penalties

    actions = [part for part in parts if part in PHRASE_ACTION_TERMS]
    ends_with_action = bool(parts) and parts[-1] in PHRASE_ACTION_TERMS
    preceding = set(parts[:-1])
    has_source = bool(
        preceding
        & (PRIMARY_OBJECT_TERMS | EXTENDED_OBJECT_TERMS | MATERIAL_TERMS)
    )
    has_detail = bool(preceding & (DETAIL_TERMS | MODIFIER_TERMS))
    if raw == "single shot":
        return "action", "review_only", {"generic_detail"}
    if parts and parts[0] in UNNATURAL_LEADS and not ends_with_action:
        return "unknown", "hard_reject", {"unnatural_order"}
    if part_set <= DETAIL_TERMS | MODIFIER_TERMS | GENERIC_COUNT_TERMS:
        return "unknown", "hard_reject", {"generic_detail"}
    if len(actions) == 1 and ends_with_action and (has_source or has_detail):
        if (
            actions[0] in EMERGING_ACTION_TERMS
            or bool(preceding & EXTENDED_OBJECT_TERMS)
            or (has_detail and not has_source)
        ):
            return "action", "review_only", penalties
        return "action", "known", penalties
    return "unknown", "hard_reject", {"unnatural_order"}


def _score(
    raw: str,
    kind: str,
    slot: str,
    policy: str,
    penalties: set[str],
    record_count: int,
    field_hit_count: int,
    field_counts: Counter[str],
    aligned_records: int,
) -> tuple[int, list[str]]:
    score = 0
    components: list[str] = []
    if record_count >= 1000:
        score += 25
        components.append("record_count>=1000 +25")
    elif record_count >= 500:
        score += 20
        components.append("record_count>=500 +20")
    elif record_count >= 100:
        score += 15
        components.append("record_count>=100 +15")
    elif record_count >= 20:
        score += 10
        components.append("record_count>=20 +10")
    if record_count and field_hit_count / record_count >= 1.5:
        score += 10
        components.append("field_diversity>=1.5 +10")
    if field_counts.get("fx_name", 0):
        score += 15
        components.append("appears_in_fx_name +15")
    if slot in {"action", "object", "material"}:
        score += 20
        components.append(f"known_{slot}_vocabulary +20")
    if aligned_records:
        score += 10
        components.append("category_aligned +10")

    parts = raw.split()
    if kind == "phrase" and parts and parts[-1] in PHRASE_ACTION_TERMS:
        score += 15
        components.append("phrase_ends_with_action +15")
        if set(parts[:-1]) & (
            PRIMARY_OBJECT_TERMS | EXTENDED_OBJECT_TERMS | MATERIAL_TERMS
        ):
            score += 20
            components.append("source_plus_action +20")

    penalty_values = {
        "metadata_noise": -30,
        "library_context": -25,
        "mic_spec": -40,
        "generic_detail": -20,
        "unnatural_order": -15,
    }
    for penalty in sorted(penalties):
        value = penalty_values[penalty]
        score += value
        components.append(f"{penalty} {value}")
    if policy == "unknown" and not penalties:
        score -= 20
        components.append("unknown_generic_token -20")
    return max(0, min(100, score)), components


def _decision(score: int, policy: str) -> str:
    if policy == "hard_reject":
        return "reject"
    if policy == "review_only":
        return "review"
    if policy == "unknown":
        return "review" if score >= 40 else "reject"
    if score >= 70:
        return "candidate"
    if score >= 40:
        return "review"
    return "reject"


def _accepted_rows(
    rows: Iterable[dict[str, object]], *, slots: set[str], kinds: set[str]
) -> list[dict[str, object]]:
    return [
        row
        for row in rows
        if row["slot_guess"] in slots
        and row["kind"] in kinds
        and row["decision"] in {"candidate", "review"}
    ]


def _write_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVIDENCE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_expanded_examples_csv(
    path: Path, rows: Iterable[dict[str, str]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPANDED_EXAMPLE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_review_candidates(
    path: Path, rows: list[dict[str, object]], threshold: int
) -> int:
    if path.name != "canonical_token_candidates.csv":
        raise ValueError(
            "BOOM candidates may only be written to canonical_token_candidates.csv"
        )
    selected = [
        row
        for row in rows
        if row["decision"] == "candidate"
        and int(row["score"]) >= threshold
        and row["slot_guess"] in {"action", "object", "material"}
    ]
    selected.sort(key=lambda row: (str(row["raw"]).count(" "), str(row["raw"])))
    candidate_rows = [_canonical_candidate_row(row) for row in selected]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANONICAL_COLUMNS)
        writer.writeheader()
        writer.writerows(candidate_rows)
    return len(candidate_rows)


def _canonical_candidate_row(row: dict[str, object]) -> dict[str, object]:
    raw = str(row["raw"])
    slot = str(row["slot_guess"])
    parts = raw.split()
    action = next((part for part in reversed(parts) if part in ACTION_TERMS), "")
    ambiguity = "high" if action in HIGH_AMBIGUITY_ACTIONS else "medium"
    is_phrase = row["kind"] == "phrase"
    return {
        "raw": raw,
        "canonical": row["canonical_guess"],
        "slot": slot,
        "lang": "en",
        "priority": 0,
        "rule_type": "phrase_low_confidence" if is_phrase else "ambiguous_single",
        "review_status": "review",
        "ambiguity": ambiguity,
        "tags": f"boom/{slot}",
        "source": "boom_mined",
        "note": (
            f"score={row['score']}; record_count={row['record_count']}; "
            "requires human review"
        ),
    }


def _write_report(
    path: Path, summary: EvidenceSummary, rows: list[dict[str, object]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# BOOM Candidate Evidence Report",
        "",
        f"- input token count: `{summary.token_count}`",
        f"- input phrase count: `{summary.phrase_count}`",
        f"- action candidate count: `{summary.action_candidate_count}`",
        f"- object candidate count: `{summary.object_candidate_count}`",
        f"- material candidate count: `{summary.material_candidate_count}`",
        (
            "- detail/modifier candidate count: "
            f"`{summary.detail_modifier_candidate_count}`"
        ),
        f"- phrase candidate count: `{summary.phrase_candidate_count}`",
        f"- rejected noise count: `{summary.rejected_noise_count}`",
        f"- expanded evidence rows: `{summary.expanded_evidence_count}`",
        f"- expanded examples: `{summary.expanded_examples_path}`",
        (
            "- approved_for_ai before expansion: "
            f"`{summary.approved_for_ai_before_expansion_count}`"
        ),
        f"- approved_for_ai after expansion: `{summary.approved_for_ai_count}`",
        f"- review-only candidates written: `{summary.written_candidate_count}`",
        "",
        "## Top accepted examples",
        "",
        *_report_rows(rows, "candidate"),
        "",
        "## Top review examples",
        "",
        *_report_rows(rows, "review"),
        "",
        "## Top rejected examples",
        "",
        *_report_rows(rows, "reject"),
        "",
        "## Scoring rule summary",
        "",
        "- record frequency: +10/+15/+20/+25 at 20/100/500/1000 records",
        "- field diversity >= 1.5: +10",
        "- appears in FXName: +15",
        "- known action/object/material vocabulary: +20",
        "- category/subcategory alignment: +10",
        "- phrase ending in action: +15; source + action: +20",
        "- metadata/code: -30; library context: -25; mic/spec: -40",
        "- detail-only: -20; unnatural phrase order: -15",
        "- score >= 70 candidate; 40-69 review; below 40 reject",
        "- review-only and hard-reject policies override numeric thresholds",
        "",
        "## Canonical token guard",
        "",
        (
            "- canonical_tokens_sha256_before: "
            f"`{summary.canonical_tokens_sha256_before}`"
        ),
        (
            "- canonical_tokens_sha256_after: "
            f"`{summary.canonical_tokens_sha256_after}`"
        ),
        "- canonical_tokens.csv changed: `no`",
        "- automatic promotion: `no`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_qa_report(
    path: Path, summary: EvidenceSummary, rows: list[dict[str, object]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    field_quality = Counter(str(row["field_quality"]) for row in rows)
    example_quality = Counter(str(row["example_quality"]) for row in rows)
    category_alignment = Counter(str(row["category_alignment"]) for row in rows)
    lines = [
        "# BOOM Evidence QA Report",
        "",
        f"- total evidence rows: `{summary.total_evidence_count}`",
        f"- expanded evidence rows: `{summary.expanded_evidence_count}`",
        (
            "- approved_for_ai before expansion: "
            f"`{summary.approved_for_ai_before_expansion_count}`"
        ),
        f"- approved_for_ai count: `{summary.approved_for_ai_count}`",
        f"- rejected_for_ai count: `{summary.blocked_for_ai_count}`",
        "- canonical_tokens.csv changed: `no`",
        "",
        "## Field quality distribution",
        "",
        *_distribution_lines(field_quality, ("high", "medium", "low")),
        "",
        "## Example quality distribution",
        "",
        *_distribution_lines(example_quality, ("high", "medium", "low")),
        "",
        "## Category alignment distribution",
        "",
        *_distribution_lines(
            category_alignment, ("aligned", "mixed", "weak", "unknown")
        ),
        "",
        "## High-risk token decisions",
        "",
    ]
    indexed = {(str(row["raw"]), str(row["kind"])): row for row in rows}
    for raw in ("hit", "shot", "gun", "ring", "whoosh"):
        row = indexed.get((raw, "token"))
        if row is None:
            lines.append(f"- {raw}: approved_for_ai=no; reason=not present in evidence")
            continue
        reason = str(row["qa_flags"] or "quality gates passed")
        lines.append(
            f"- {raw}: approved_for_ai={row['approved_for_ai']}; reason={reason}; "
            f"field_quality={row['field_quality']}; "
            f"category_alignment={row['category_alignment']}"
        )
    lines.extend(
        [
            "",
            "## Top approved examples",
            "",
            *_qa_example_lines(rows, approved="yes"),
            "",
            "## Top blocked examples",
            "",
            *_qa_example_lines(rows, approved="no"),
            "",
            "## Canonical token guard",
            "",
            (
                "- canonical_tokens_sha256_before: "
                f"`{summary.canonical_tokens_sha256_before}`"
            ),
            (
                "- canonical_tokens_sha256_after: "
                f"`{summary.canonical_tokens_sha256_after}`"
            ),
            "- canonical_tokens.csv changed: `no`",
            "- AI invoked: `no`",
            "- automatic promotion: `no`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _distribution_lines(counts: Counter[str], values: tuple[str, ...]) -> list[str]:
    return [f"- {value}: `{counts[value]}`" for value in values]


def _qa_example_lines(
    rows: list[dict[str, object]], *, approved: str
) -> list[str]:
    selected = sorted(
        (row for row in rows if row["approved_for_ai"] == approved),
        key=lambda row: (-int(row["score"]), -int(row["record_count"]), row["raw"]),
    )[:10]
    if not selected:
        return ["- none"]
    return [
        (
            f"- `{row['raw']}`: field={row['field_quality']}, "
            f"example={row['example_quality']}, "
            f"category={row['category_alignment']}, "
            f"flags={row['qa_flags'] or 'none'}"
        )
        for row in selected
    ]


def _report_rows(rows: list[dict[str, object]], decision: str) -> list[str]:
    selected = sorted(
        (row for row in rows if row["decision"] == decision),
        key=lambda row: (-int(row["score"]), -int(row["record_count"]), row["raw"]),
    )[:10]
    if not selected:
        return ["- none"]
    return [
        (
            f"- `{row['raw']}` ({row['kind']}, {row['slot_guess']}): "
            f"score={row['score']}, records={row['record_count']}"
        )
        for row in selected
    ]


def _format_example(row: dict[str, str]) -> str:
    payload = {
        "fx_name": _shorten(row.get("fx_name", ""), 80),
        "description": _shorten(row.get("description", ""), 140),
        "category": _shorten(
            "/".join(
                value
                for value in (row.get("category", ""), row.get("subcategory", ""))
                if value
            ),
            60,
        ),
        "cat_id": _shorten(row.get("cat_id", ""), 32),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _format_field_counts(counts: Counter[str]) -> str:
    return "; ".join(f"{field}={counts.get(field, 0)}" for field in MINING_FIELDS)


def _counter_samples(counts: Counter[str], limit: int = 3) -> str:
    return "; ".join(
        value for value, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    )


def _normalized_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.casefold())
    normalized: set[str] = set(words)
    for word in words:
        if word.endswith("ies") and len(word) > 4:
            normalized.add(word[:-3] + "y")
        elif word.endswith("s") and len(word) > 3:
            normalized.add(word[:-1])
    return normalized


def _title_case(raw: str) -> str:
    return " ".join(part[:1].upper() + part[1:].lower() for part in raw.split())


def _shorten(value: str, limit: int) -> str:
    clean = " ".join(str(value or "").split())
    return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "…"


def _to_nonnegative_int(value: str | None, path: Path) -> int:
    try:
        number = int(value or "0")
    except ValueError as exc:
        raise ValueError(f"{path} contains a non-integer count: {value!r}") from exc
    if number < 0:
        raise ValueError(f"{path} contains a negative count: {number}")
    return number


def _safe_int(value: str | None, default: int) -> int:
    try:
        return int(value or "")
    except ValueError:
        return default


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-tokens", type=Path, default=DEFAULT_MINING_DIR / "top_tokens.csv")
    parser.add_argument("--top-phrases", type=Path, default=DEFAULT_MINING_DIR / "top_phrases.csv")
    parser.add_argument("--token-examples", type=Path, default=DEFAULT_MINING_DIR / "token_examples.csv")
    parser.add_argument("--phrase-examples", type=Path, default=DEFAULT_MINING_DIR / "phrase_examples.csv")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--qa-report", type=Path, default=DEFAULT_QA_REPORT)
    parser.add_argument("--write-candidates", type=Path)
    parser.add_argument("--candidate-threshold", type=int, default=70)
    parser.add_argument("--max-examples", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        summary = build_candidate_evidence(
            args.top_tokens,
            args.top_phrases,
            args.token_examples,
            args.phrase_examples,
            args.db,
            args.canonical,
            args.output_dir,
            args.report,
            args.qa_report,
            write_candidates=args.write_candidates,
            candidate_threshold=args.candidate_threshold,
            max_examples_per_candidate=args.max_examples,
        )
    except (FileNotFoundError, ValueError, RuntimeError, sqlite3.DatabaseError) as exc:
        parser.error(str(exc))
    print(
        f"tokens={summary.token_count} phrases={summary.phrase_count} "
        f"actions={summary.action_candidate_count} objects={summary.object_candidate_count} "
        f"materials={summary.material_candidate_count} phrase_candidates={summary.phrase_candidate_count} "
        f"rejected={summary.rejected_noise_count} "
        f"approved_for_ai={summary.approved_for_ai_count} "
        f"canonical_changed={str(summary.canonical_tokens_changed).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
