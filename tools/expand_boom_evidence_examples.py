#!/usr/bin/env python3
"""Expand BOOM candidate evidence examples from SQLite before AI prompt packing."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fxengine.canonical_db import DEFAULT_CANONICAL_PATH  # noqa: E402
from tools.build_boom_candidate_evidence import (  # noqa: E402
    EVIDENCE_COLUMNS,
    EXAMPLE_SOURCE_PRIORITY,
    _record_category_aligned,
)

DEFAULT_DB = ROOT / "data" / "boomone" / "boomone_records.sqlite"
DEFAULT_CANDIDATE_EVIDENCE = ROOT / "exports" / "boomone_candidates" / "candidate_evidence.csv"
DEFAULT_OUTPUT_DIR = ROOT / "exports" / "boomone_candidates"
DEFAULT_REPORT = ROOT / "reports" / "boom_evidence_expansion_report.md"
DEFAULT_CANONICAL = DEFAULT_CANONICAL_PATH

EXPANDED_EXAMPLE_COLUMNS = (
    "raw", "canonical_guess", "example_rank", "match_field", "match_quality",
    "fx_name", "description", "keywords", "filename", "cat_id", "category",
    "subcategory", "source_file", "flags",
)
SEARCH_FIELDS = ("fx_name", "keywords", "description", "filename", "category", "subcategory", "cat_id")
HIGH_RISK_TERMS = {"hit", "shot", "ring", "drop", "break", "crack", "roll", "fire", "gun", "body", "hard", "soft", "low", "high", "single", "short", "long", "movement", "tonal"}


@dataclass(frozen=True)
class ExpansionSummary:
    total_candidate_rows: int
    expanded_evidence_rows: int
    average_examples_per_candidate: float
    before_approved_for_ai_count: int
    after_approved_for_ai_count: int
    expanded_examples_path: str
    expanded_candidate_evidence_path: str
    report_path: str
    canonical_tokens_sha256_before: str
    canonical_tokens_sha256_after: str
    canonical_tokens_changed: bool


def expand_candidate_evidence(
    candidate_evidence_path: Path = DEFAULT_CANDIDATE_EVIDENCE,
    db_path: Path = DEFAULT_DB,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    report_path: Path = DEFAULT_REPORT,
    canonical_path: Path = DEFAULT_CANONICAL,
    *,
    max_examples_per_candidate: int = 20,
) -> ExpansionSummary:
    candidate_evidence_path = Path(candidate_evidence_path)
    db_path = Path(db_path)
    output_dir = Path(output_dir)
    report_path = Path(report_path)
    canonical_path = Path(canonical_path)
    for path in (candidate_evidence_path, db_path, canonical_path):
        if not path.is_file():
            raise FileNotFoundError(f"Required input not found: {path}")
    if max_examples_per_candidate < 1:
        raise ValueError("max_examples_per_candidate must be positive")

    canonical_before = _sha256(canonical_path)
    candidates = _read_candidate_rows(candidate_evidence_path)
    before_approved = sum(row.get("approved_for_ai") == "yes" for row in candidates)
    expanded_rows: list[dict[str, str]] = []
    rescored_rows: list[dict[str, object]] = []

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        _assert_table(connection)
        for row in candidates:
            examples = expand_examples_for_candidate(
                connection,
                row["raw"],
                row.get("canonical_guess", ""),
                max_examples=max_examples_per_candidate,
            )
            expanded_rows.extend(examples)
            rescored_rows.append(_rescore_candidate_row(row, examples))
    finally:
        connection.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    expanded_examples_path = output_dir / "expanded_examples.csv"
    expanded_candidate_path = output_dir / "candidate_evidence_expanded.csv"
    _write_csv(expanded_examples_path, EXPANDED_EXAMPLE_COLUMNS, expanded_rows)
    _write_csv(expanded_candidate_path, EVIDENCE_COLUMNS, rescored_rows)

    canonical_after = _sha256(canonical_path)
    if canonical_after != canonical_before:
        raise RuntimeError("canonical_tokens.csv changed while expanding evidence")
    summary = ExpansionSummary(
        total_candidate_rows=len(candidates),
        expanded_evidence_rows=len(expanded_rows),
        average_examples_per_candidate=len(expanded_rows) / len(candidates) if candidates else 0.0,
        before_approved_for_ai_count=before_approved,
        after_approved_for_ai_count=sum(row.get("approved_for_ai") == "yes" for row in rescored_rows),
        expanded_examples_path=str(expanded_examples_path),
        expanded_candidate_evidence_path=str(expanded_candidate_path),
        report_path=str(report_path),
        canonical_tokens_sha256_before=canonical_before,
        canonical_tokens_sha256_after=canonical_after,
        canonical_tokens_changed=False,
    )
    _write_report(report_path, summary, rescored_rows, expanded_rows)
    return summary


def expand_examples_for_candidate(
    connection: sqlite3.Connection,
    raw: str,
    canonical_guess: str,
    *,
    max_examples: int = 20,
) -> list[dict[str, str]]:
    query = f"%{raw}%"
    records = connection.execute(
        """
        SELECT record_id, filename, fx_name, description, keywords, cat_id,
               category, subcategory, source_file
        FROM boomone_records
        WHERE fx_name LIKE ? COLLATE NOCASE
           OR keywords LIKE ? COLLATE NOCASE
           OR description LIKE ? COLLATE NOCASE
           OR filename LIKE ? COLLATE NOCASE
           OR category LIKE ? COLLATE NOCASE
           OR subcategory LIKE ? COLLATE NOCASE
           OR cat_id LIKE ? COLLATE NOCASE
        ORDER BY record_id
        """,
        [query] * len(SEARCH_FIELDS),
    ).fetchall()
    examples = []
    for record in records:
        field = _best_match_field(raw, record)
        if not field:
            continue
        examples.append(_expanded_row(raw, canonical_guess, record, field))
    examples.sort(key=_example_sort_key)
    selected = examples[:max_examples]
    for index, row in enumerate(selected, start=1):
        row["example_rank"] = str(index)
    return selected


def select_best_examples(examples: list[dict[str, str]], *, limit: int = 3) -> list[dict[str, str]]:
    selected = []
    seen_payloads: set[str] = set()
    seen_fx: set[str] = set()
    for row in sorted(examples, key=_example_sort_key):
        payload = "|".join(row.get(field, "").casefold() for field in ("fx_name", "filename", "source_file"))
        fx_name = row.get("fx_name", "").casefold()
        if payload in seen_payloads or fx_name in seen_fx:
            continue
        selected.append(row)
        seen_payloads.add(payload)
        if fx_name:
            seen_fx.add(fx_name)
        if len(selected) >= limit:
            break
    return selected


def score_example_quality(examples: list[dict[str, str]]) -> str:
    selected = select_best_examples(examples)
    trusted = sum(row["match_field"] in {"fx_name", "keywords"} for row in selected)
    noisy = any(_has_major_noise(row) for row in selected)
    if not selected or noisy:
        return "low"
    if len(selected) >= 3 and trusted:
        return "high"
    if len(selected) >= 2:
        return "medium"
    return "low"


def _rescore_candidate_row(row: dict[str, str], examples: list[dict[str, str]]) -> dict[str, object]:
    selected = select_best_examples(examples)
    formatted = [_format_example(row) for row in selected]
    formatted.extend([""] * (3 - len(formatted)))
    field_counts = Counter(example["match_field"] for example in examples)
    category_alignment = _category_alignment(row["raw"], examples)
    field_quality = _field_quality(field_counts, selected, category_alignment)
    example_quality = score_example_quality(examples)
    approved, flags = _qa_decision(row, field_counts, selected, field_quality, example_quality, category_alignment)
    updated = dict(row)
    updated.update(
        {
            "source_fields": _format_field_counts(field_counts),
            "example_1": formatted[0],
            "example_2": formatted[1],
            "example_3": formatted[2],
            "catid_samples": _samples(example["cat_id"] for example in examples),
            "category_samples": _samples("/".join(v for v in (example["category"], example["subcategory"]) if v) for example in examples),
            "source_files": _samples(example["source_file"] for example in examples),
            "fx_name_hits": field_counts.get("fx_name", 0),
            "description_hits": field_counts.get("description", 0),
            "keywords_hits": field_counts.get("keywords", 0),
            "filename_hits": field_counts.get("filename", 0),
            "field_quality": field_quality,
            "example_quality": example_quality,
            "category_alignment": category_alignment,
            "approved_for_ai": approved,
            "qa_flags": ";".join(flags),
        }
    )
    return {column: updated.get(column, "") for column in EVIDENCE_COLUMNS}


def _qa_decision(row: dict[str, str], counts: Counter[str], selected: list[dict[str, str]], field_quality: str, example_quality: str, category_alignment: str) -> tuple[str, list[str]]:
    raw = row["raw"]
    parts = set(raw.split())
    flags = [flag for flag in row.get("qa_flags", "").split(";") if flag]
    trusted_hits = counts.get("fx_name", 0) + counts.get("keywords", 0)
    if parts & HIGH_RISK_TERMS and "ambiguous_token" not in flags:
        flags.append("ambiguous_token")
    if trusted_hits == 0 and counts.get("description", 0):
        flags.append("description_only")
    if trusted_hits == 0 and counts.get("filename", 0):
        flags.append("filename_only")
    if category_alignment == "weak":
        flags.append("category_mismatch")
    elif category_alignment == "mixed":
        flags.append("category_mixed")
    elif category_alignment == "unknown":
        flags.append("category_unknown")
    if any(_has_major_noise(example) for example in selected):
        flags.append("expanded_noise_context")
    approved = (
        row.get("decision") in {"candidate", "review"}
        and row.get("slot_guess") not in {"detail", "modifier", "unknown"}
        and field_quality in {"high", "medium"}
        and example_quality in {"high", "medium"}
        and category_alignment in {"aligned", "mixed"}
        and row.get("existing_canonical_status") != "existing_conflict"
        and "expanded_noise_context" not in flags
    )
    if parts & HIGH_RISK_TERMS:
        approved = approved and field_quality == "high" and category_alignment == "aligned"
    return ("yes" if approved else "no"), list(dict.fromkeys(flags))


def _expanded_row(raw: str, canonical_guess: str, record: sqlite3.Row, field: str) -> dict[str, str]:
    row = {
        "raw": raw,
        "canonical_guess": canonical_guess,
        "example_rank": "0",
        "match_field": field,
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
    flags = _flags(raw, row, field)
    row["flags"] = ";".join(flags)
    row["match_quality"] = _match_quality(raw, row, field, flags)
    return row


def _flags(raw: str, row: dict[str, str], field: str) -> list[str]:
    flags = []
    if field == "description":
        flags.append("description_only")
    if field == "filename":
        flags.append("filename_only")
    if not _record_category_aligned(raw, row["category"], row["subcategory"], row["cat_id"]):
        flags.append("category_mismatch")
    text = " ".join(row.values()).casefold()
    if "shotgun microphone" in text or "shotgun mic" in text:
        flags.append("shotgun_microphone")
    if any(term in text for term in ("tape gun", "glue gun", "tool gun")) and not _record_category_aligned("gun", row["category"], row["subcategory"], row["cat_id"]):
        flags.append("tool_gun_context")
    if row["category"].casefold().startswith("ambience") and field == "description":
        flags.append("ambience_context")
    if any(term in text for term in ("microphone", "frequency response")):
        flags.append("metadata_context")
    return list(dict.fromkeys(flags))


def _match_quality(raw: str, row: dict[str, str], field: str, flags: list[str]) -> str:
    if _has_major_noise({"flags": ";".join(flags)}):
        return "low"
    if field == "fx_name":
        return "high"
    if field == "keywords" and _record_category_aligned(raw, row["category"], row["subcategory"], row["cat_id"]):
        return "high"
    if field == "description" and "category_mismatch" not in flags:
        return "medium"
    return "low"


def _field_quality(counts: Counter[str], selected: list[dict[str, str]], alignment: str) -> str:
    trusted = counts.get("fx_name", 0) + counts.get("keywords", 0)
    if counts.get("fx_name", 0) and alignment == "aligned" and len(selected) >= 2:
        return "high"
    if trusted:
        return "medium"
    return "low"


def _category_alignment(raw: str, examples: list[dict[str, str]]) -> str:
    categorized = [row for row in examples if row["category"] or row["subcategory"] or row["cat_id"]]
    if not categorized:
        return "unknown"
    aligned = [row for row in categorized if _record_category_aligned(raw, row["category"], row["subcategory"], row["cat_id"])]
    if len(aligned) / len(categorized) >= 0.6:
        return "aligned"
    if aligned:
        return "mixed"
    return "weak"


def _best_match_field(raw: str, record: sqlite3.Row) -> str:
    for field in ("fx_name", "keywords", "description", "filename", "category", "subcategory", "cat_id"):
        if _contains(raw, str(record[field] or "")):
            return field
    return ""


def _contains(raw: str, text: str) -> bool:
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(raw.casefold()) + r"(?![a-z0-9])", text.casefold()))


def _example_sort_key(row: dict[str, str]) -> tuple[int, int, int, str, str]:
    quality = {"high": 0, "medium": 1, "low": 2}
    return (
        EXAMPLE_SOURCE_PRIORITY.get(row["match_field"], 99),
        quality.get(row["match_quality"], 99),
        len([flag for flag in row["flags"].split(";") if flag]),
        row["source_file"],
        row["fx_name"],
    )


def _has_major_noise(row: dict[str, str]) -> bool:
    flags = set(flag for flag in row.get("flags", "").split(";") if flag)
    return bool(flags & {"shotgun_microphone", "tool_gun_context", "ambience_context", "metadata_context"})


def _format_example(row: dict[str, str]) -> str:
    return json.dumps(
        {
            "fx_name": _shorten(row.get("fx_name", ""), 80),
            "description": _shorten(row.get("description", ""), 140),
            "category": _shorten("/".join(v for v in (row.get("category", ""), row.get("subcategory", "")) if v), 60),
            "cat_id": _shorten(row.get("cat_id", ""), 32),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _read_candidate_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not set(EVIDENCE_COLUMNS) <= set(reader.fieldnames):
            raise ValueError(f"{path} is missing candidate evidence columns")
        return [{key: value or "" for key, value in row.items()} for row in reader]


def _assert_table(connection: sqlite3.Connection) -> None:
    exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='boomone_records'").fetchone()
    if exists is None:
        raise ValueError("boomone_records table is missing")


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_report(path: Path, summary: ExpansionSummary, rows: list[dict[str, object]], expanded: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    field_quality = Counter(str(row["field_quality"]) for row in rows)
    example_quality = Counter(str(row["example_quality"]) for row in rows)
    category_alignment = Counter(str(row["category_alignment"]) for row in rows)
    match_field = Counter(row["match_field"] for row in expanded)
    match_quality = Counter(row["match_quality"] for row in expanded)
    indexed = {str(row["raw"]): row for row in rows}
    risk_lines = []
    for raw in ("hit", "shot", "gun", "ring", "whoosh"):
        row = indexed.get(raw)
        risk_lines.append(f"- {raw}: approved_for_ai={row['approved_for_ai']}; flags={row.get('qa_flags') or 'none'}" if row else f"- {raw}: not present")
    lines = [
        "# BOOM Evidence Expansion Report",
        "",
        f"- total candidate rows: `{summary.total_candidate_rows}`",
        f"- expanded evidence rows: `{summary.expanded_evidence_rows}`",
        f"- average examples per candidate: `{summary.average_examples_per_candidate:.2f}`",
        f"- before approved_for_ai count: `{summary.before_approved_for_ai_count}`",
        f"- after approved_for_ai count: `{summary.after_approved_for_ai_count}`",
        "- canonical_tokens.csv changed: `no`",
        "- AI invoked: `no`",
        "- automatic promotion: `no`",
        "",
        "## Match field distribution",
        "",
        *_named_distribution_lines(match_field),
        "",
        "## Match quality distribution",
        "",
        *_named_distribution_lines(match_quality),
        "",
        "## Field quality distribution",
        "",
        *_named_distribution_lines(field_quality),
        "",
        "## Example quality distribution",
        "",
        *_named_distribution_lines(example_quality),
        "",
        "## Category alignment distribution",
        "",
        *_named_distribution_lines(category_alignment),
        "",
        "## High-risk token before/after decision",
        "",
        *risk_lines,
        "",
        "## Canonical token guard",
        "",
        f"- canonical_tokens_sha256_before: `{summary.canonical_tokens_sha256_before}`",
        f"- canonical_tokens_sha256_after: `{summary.canonical_tokens_sha256_after}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _named_distribution_lines(counts: Counter[str]) -> list[str]:
    if not counts:
        return ["- none"]
    return [f"- {key}: `{counts[key]}`" for key in sorted(counts)]


def _samples(values: Iterable[str], limit: int = 5) -> str:
    return "; ".join(value for value, _count in Counter(v for v in values if v).most_common(limit))


def _format_field_counts(counts: Counter[str]) -> str:
    return "; ".join(f"{field}={counts.get(field, 0)}" for field in ("fx_name", "description", "keywords", "filename"))


def _shorten(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: max(0, limit - 1)].rstrip() + "…"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-evidence", type=Path, default=DEFAULT_CANDIDATE_EVIDENCE)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--max-examples", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        summary = expand_candidate_evidence(
            args.candidate_evidence,
            args.db,
            args.output_dir,
            args.report,
            args.canonical,
            max_examples_per_candidate=args.max_examples,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(
        f"candidates={summary.total_candidate_rows} expanded_examples={summary.expanded_evidence_rows} "
        f"approved_before={summary.before_approved_for_ai_count} approved_after={summary.after_approved_for_ai_count} "
        f"canonical_changed={str(summary.canonical_tokens_changed).lower()} ai_invoked=no promote=no"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
