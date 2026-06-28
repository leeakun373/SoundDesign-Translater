#!/usr/bin/env python3
"""Build a local JSONL prompt pack for later conservative AI alias generation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE_DIR = ROOT / "exports" / "boomone_candidates"
DEFAULT_OUTPUT_DIR = ROOT / "exports" / "ai_alias_prompt_pack"
DEFAULT_REPORT = ROOT / "reports" / "ai_alias_prompt_pack_report.md"
DEFAULT_CANONICAL = ROOT / "fxengine" / "data" / "canonical_tokens.csv"
AI_INSTRUCTION = (
    "Generate conservative Chinese aliases for a sound-design FXName token. "
    "Do not translate freely. Return only aliases that a Chinese sound designer "
    "would actually type."
)
EXPECTED_COLUMNS = (
    "raw",
    "canonical",
    "slot",
    "lang",
    "priority",
    "rule_type",
    "review_status",
    "ambiguity",
    "tags",
    "source",
    "note",
)


@dataclass(frozen=True)
class PromptPackSummary:
    item_count: int
    input_candidate_count: int
    approved_for_ai_count: int
    skipped_count: int
    skip_reason_counts: dict[str, int]
    jsonl_path: str
    preview_path: str
    report_path: str
    canonical_tokens_sha256_before: str
    canonical_tokens_sha256_after: str
    canonical_tokens_changed: bool
    ai_invoked: bool = False


def build_alias_prompt_pack(
    action_candidates_path: Path = DEFAULT_CANDIDATE_DIR / "action_candidates.csv",
    phrase_candidates_path: Path = DEFAULT_CANDIDATE_DIR / "phrase_candidates.csv",
    object_candidates_path: Path = DEFAULT_CANDIDATE_DIR / "object_candidates.csv",
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    report_path: Path = DEFAULT_REPORT,
    canonical_path: Path = DEFAULT_CANONICAL,
    *,
    preview_limit: int = 20,
) -> PromptPackSummary:
    """Write JSONL/Markdown inputs only; this function never invokes a model."""
    input_specs = (
        (Path(action_candidates_path), "action"),
        (Path(phrase_candidates_path), "action"),
        (Path(object_candidates_path), "object"),
    )
    missing = [path for path, _slot in input_specs if not path.is_file()]
    canonical_path = Path(canonical_path)
    if not canonical_path.is_file():
        missing.append(canonical_path)
    if missing:
        raise FileNotFoundError(f"Required input not found: {missing[0]}")
    if preview_limit < 1:
        raise ValueError("preview_limit must be positive")

    canonical_before = _sha256(canonical_path)
    ranked: list[tuple[tuple[int, int, str, str], dict[str, object]]] = []
    seen: set[tuple[str, str]] = set()
    input_candidate_count = 0
    approved_for_ai_count = 0
    skipped_count = 0
    skip_reason_counts: Counter[str] = Counter()
    for path, default_slot in input_specs:
        for row in _read_candidates(path):
            input_candidate_count += 1
            if (
                row.get("approved_for_ai") != "yes"
                or row.get("decision") not in {"candidate", "review"}
            ):
                skipped_count += 1
                skip_reason_counts[_skip_reason(row)] += 1
                continue
            approved_for_ai_count += 1
            canonical = (row.get("canonical_guess") or "").strip()
            slot = (row.get("slot_guess") or default_slot).strip() or default_slot
            if not canonical:
                continue
            key = (canonical.casefold(), slot)
            if key in seen:
                skipped_count += 1
                skip_reason_counts["duplicate_approved_candidate"] += 1
                continue
            seen.add(key)
            item = {
                "canonical": canonical,
                "slot": slot,
                "candidate_type": (row.get("kind") or "token").strip(),
                "record_count": _safe_int(row.get("record_count")),
                "examples": _parse_examples(row),
                "instruction": AI_INSTRUCTION,
            }
            rank = (
                0 if row.get("decision") == "candidate" else 1,
                -_safe_int(row.get("score")),
                canonical.casefold(),
                slot,
            )
            ranked.append((rank, item))

    ranked.sort(key=lambda pair: pair[0])
    items = [item for _rank, item in ranked]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "alias_prompt_items.jsonl"
    preview_path = output_dir / "alias_prompt_preview.md"
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    _write_preview(preview_path, items[:preview_limit])

    canonical_after = _sha256(canonical_path)
    if canonical_after != canonical_before:
        raise RuntimeError("canonical_tokens.csv changed while building prompt pack")
    summary = PromptPackSummary(
        item_count=len(items),
        input_candidate_count=input_candidate_count,
        approved_for_ai_count=approved_for_ai_count,
        skipped_count=skipped_count,
        skip_reason_counts=dict(sorted(skip_reason_counts.items())),
        jsonl_path=str(jsonl_path),
        preview_path=str(preview_path),
        report_path=str(report_path),
        canonical_tokens_sha256_before=canonical_before,
        canonical_tokens_sha256_after=canonical_after,
        canonical_tokens_changed=False,
    )
    _write_report(Path(report_path), summary, input_specs)
    return summary


def _read_candidates(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "canonical_guess",
            "kind",
            "slot_guess",
            "record_count",
            "score",
            "decision",
            "approved_for_ai",
            "qa_flags",
            "example_1",
            "example_2",
            "example_3",
        }
        if not reader.fieldnames or not required <= set(reader.fieldnames):
            raise ValueError(f"{path} is missing required candidate evidence columns")
        return [{key: value or "" for key, value in row.items()} for row in reader]


def _skip_reason(row: dict[str, str]) -> str:
    if row.get("decision") not in {"candidate", "review"}:
        return "not_candidate_or_review"
    flags = [flag for flag in row.get("qa_flags", "").split(";") if flag]
    priorities = (
        "shotgun_microphone",
        "tool_gun_context",
        "generic_description_hit",
        "ambience_ring",
        "detail_modifier",
        "rejected_evidence",
        "existing_conflict",
        "category_mismatch",
        "category_unknown",
        "description_only",
        "filename_only",
        "duplicate_examples",
        "insufficient_unique_examples",
        "ambiguous_token",
    )
    return next((reason for reason in priorities if reason in flags), "not_approved_for_ai")


def _parse_examples(row: dict[str, str]) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    for field in ("example_1", "example_2", "example_3"):
        raw = row.get(field, "").strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"fx_name": raw, "description": "", "category": "", "cat_id": ""}
        if not isinstance(payload, dict):
            payload = {"fx_name": raw, "description": "", "category": "", "cat_id": ""}
        examples.append(
            {
                "fx_name": str(payload.get("fx_name", "")),
                "description": str(payload.get("description", "")),
                "category": str(payload.get("category", "")),
                "cat_id": str(payload.get("cat_id", "")),
            }
        )
    return examples


def _write_preview(path: Path, items: list[dict[str, object]]) -> None:
    lines = [
        "# AI Alias Prompt Preview",
        "",
        "This file is a local input preview. No AI service was called.",
        "",
        "## Required output format",
        "",
        "```csv",
        ",".join(EXPECTED_COLUMNS),
        "```",
        "",
        "Output constraints:",
        "",
        "- `review_status` must be `review`.",
        "- `source` must be `ai_candidate`.",
        "- `priority` must be `0`.",
        "- Never output `keep`.",
        "- Do not output free-translation sentences or metadata descriptions.",
        "- Do not overwrite `canonical_tokens.csv`.",
    ]
    for index, item in enumerate(items, start=1):
        lines.extend(
            [
                "",
                f"## Item {index}: {item['canonical']}",
                "",
                f"- canonical: `{item['canonical']}`",
                f"- slot: `{item['slot']}`",
                f"- candidate_type: `{item['candidate_type']}`",
                f"- record_count: `{item['record_count']}`",
                f"- AI instruction: {item['instruction']}",
                "- examples:",
            ]
        )
        examples = item.get("examples", [])
        if examples:
            for example in examples:
                lines.append(
                    "  - "
                    + json.dumps(example, ensure_ascii=False, separators=(",", ":"))
                )
        else:
            lines.append("  - none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_report(
    path: Path,
    summary: PromptPackSummary,
    input_specs: tuple[tuple[Path, str], ...],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# AI Alias Prompt Pack Report",
        "",
        f"- input_candidate_count: `{summary.input_candidate_count}`",
        f"- approved_for_ai_count: `{summary.approved_for_ai_count}`",
        f"- skipped_count: `{summary.skipped_count}`",
        "- skip_reason_counts: `"
        + json.dumps(summary.skip_reason_counts, sort_keys=True)
        + "`",
        f"- prompt_pack_item_count: `{summary.item_count}`",
        f"- JSONL: `{summary.jsonl_path}`",
        f"- preview: `{summary.preview_path}`",
        "- AI invoked: `no`",
        "- required review_status: `review`",
        "- required source: `ai_candidate`",
        "- required priority: `0`",
        "- automatic promotion: `no`",
        "- canonical_tokens.csv changed: `no`",
        "",
        "## Skip reason counts",
        "",
        *(
            f"- {reason}: `{count}`"
            for reason, count in summary.skip_reason_counts.items()
        ),
        "",
        "## Inputs",
        "",
        *(f"- `{path}`" for path, _slot in input_specs),
        "",
        "## Canonical token guard",
        "",
        f"- canonical_tokens_sha256_before: `{summary.canonical_tokens_sha256_before}`",
        f"- canonical_tokens_sha256_after: `{summary.canonical_tokens_sha256_after}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _safe_int(value: str | None) -> int:
    try:
        return int(value or "0")
    except ValueError:
        return 0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--action-candidates",
        type=Path,
        default=DEFAULT_CANDIDATE_DIR / "action_candidates.csv",
    )
    parser.add_argument(
        "--phrase-candidates",
        type=Path,
        default=DEFAULT_CANDIDATE_DIR / "phrase_candidates.csv",
    )
    parser.add_argument(
        "--object-candidates",
        type=Path,
        default=DEFAULT_CANDIDATE_DIR / "object_candidates.csv",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--preview-limit", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        summary = build_alias_prompt_pack(
            args.action_candidates,
            args.phrase_candidates,
            args.object_candidates,
            args.output_dir,
            args.report,
            args.canonical,
            preview_limit=args.preview_limit,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(
        f"items={summary.item_count} approved={summary.approved_for_ai_count} "
        f"skipped={summary.skipped_count} ai_invoked=no "
        f"canonical_changed={str(summary.canonical_tokens_changed).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
