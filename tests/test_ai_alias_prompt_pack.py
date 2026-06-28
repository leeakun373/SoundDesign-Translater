"""AI alias prompt pack remains local, structured, and review-only by contract."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from fxengine.canonical_db import DEFAULT_CANONICAL_PATH
from tools.build_ai_alias_prompt_pack import (
    AI_INSTRUCTION,
    EXPECTED_COLUMNS,
    build_alias_prompt_pack,
)
from tools.build_boom_candidate_evidence import EVIDENCE_COLUMNS


def _evidence_row(
    raw: str, canonical: str, kind: str, slot: str, score: int
) -> dict[str, object]:
    example = json.dumps(
        {
            "fx_name": canonical,
            "description": f"A {raw} sound",
            "category": "TEST/IMPACT",
            "cat_id": "TESTImpt",
        },
        separators=(",", ":"),
    )
    return {
        "raw": raw,
        "canonical_guess": canonical,
        "kind": kind,
        "slot_guess": slot,
        "record_count": 123,
        "field_hit_count": 200,
        "example_count": 1,
        "score": score,
        "decision": "candidate" if score >= 70 else "review",
        "reason": "test evidence",
        "source_fields": "fx_name=1; description=1; keywords=0; filename=0",
        "example_1": example,
        "example_2": "",
        "example_3": "",
        "catid_samples": "TESTImpt",
        "category_samples": "TEST/IMPACT",
        "source_files": "synthetic.csv",
    }


def _write_candidates(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVIDENCE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def test_prompt_pack_writes_jsonl_without_invoking_ai(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "candidates"
    _write_candidates(
        candidate_dir / "action_candidates.csv",
        [_evidence_row("knock", "Knock", "token", "action", 75)],
    )
    _write_candidates(
        candidate_dir / "phrase_candidates.csv",
        [_evidence_row("metal door slam", "Metal Door Slam", "phrase", "action", 90)],
    )
    _write_candidates(
        candidate_dir / "object_candidates.csv",
        [_evidence_row("door", "Door", "token", "object", 70)],
    )
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    canonical_before = canonical_path.read_bytes()

    summary = build_alias_prompt_pack(
        candidate_dir / "action_candidates.csv",
        candidate_dir / "phrase_candidates.csv",
        candidate_dir / "object_candidates.csv",
        tmp_path / "prompt_pack",
        tmp_path / "prompt_report.md",
        canonical_path,
    )

    lines = Path(summary.jsonl_path).read_text(encoding="utf-8").splitlines()
    items = [json.loads(line) for line in lines]
    assert summary.item_count == len(items) == 3
    assert summary.ai_invoked is False
    assert canonical_path.read_bytes() == canonical_before
    assert {item["canonical"] for item in items} == {"Knock", "Metal Door Slam", "Door"}
    assert {item["instruction"] for item in items} == {AI_INSTRUCTION}
    assert all(
        set(example) == {"fx_name", "description", "category", "cat_id"}
        for item in items
        for example in item["examples"]
    )


def test_prompt_preview_requires_review_ai_candidate_rows(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "candidates"
    for filename, rows in (
        (
            "action_candidates.csv",
            [_evidence_row("knock", "Knock", "token", "action", 75)],
        ),
        ("phrase_candidates.csv", []),
        ("object_candidates.csv", []),
    ):
        _write_candidates(candidate_dir / filename, rows)
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())

    summary = build_alias_prompt_pack(
        candidate_dir / "action_candidates.csv",
        candidate_dir / "phrase_candidates.csv",
        candidate_dir / "object_candidates.csv",
        tmp_path / "prompt_pack",
        tmp_path / "prompt_report.md",
        canonical_path,
    )
    preview = Path(summary.preview_path).read_text(encoding="utf-8")
    report = Path(summary.report_path).read_text(encoding="utf-8")

    assert ",".join(EXPECTED_COLUMNS) in preview
    assert "`review_status` must be `review`" in preview
    assert "`source` must be `ai_candidate`" in preview
    assert "`priority` must be `0`" in preview
    assert "Never output `keep`" in preview
    assert "AI invoked: `no`" in report
    assert "canonical_tokens.csv changed: `no`" in report

