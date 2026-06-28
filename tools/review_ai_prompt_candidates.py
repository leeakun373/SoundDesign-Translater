#!/usr/bin/env python3
"""Machine-review approved AI prompt candidates before alias generation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE = ROOT / "exports" / "boomone_candidates" / "candidate_evidence.csv"
DEFAULT_EXPANDED = ROOT / "exports" / "boomone_candidates" / "expanded_examples.csv"
DEFAULT_PROMPT_ROOT = ROOT / "exports" / "ai_alias_prompt_pack"
DEFAULT_CSV_OUT = DEFAULT_PROMPT_ROOT / "reviewed_prompt_candidates.csv"
DEFAULT_REPORT = ROOT / "reports" / "ai_prompt_candidate_review.md"
DEFAULT_CANONICAL = ROOT / "fxengine" / "data" / "canonical_tokens.csv"

PROMPT_MODES = ("new_candidate", "alias_expansion")
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
IMPACT_CATEGORIES = {"FIGHT/IMPACT", "METAL/IMPACT", "DESIGNED/IMPACT", "CARTOON/IMPACT", "ROCKS/IMPACT"}
GUN_WEAPON_CATEGORIES = {"GUNS/RIFLE", "GUNS/PISTOL", "GUNS/SHOTGUN", "GUNS/MACHINE GUN"}
GUN_ARTILLERY_MARKERS = ("cannon", "long gun", "artillery")
TOOL_GUN_MARKERS = ("tape gun", "glue gun", "tool gun")
SQUEAK_POSITIVE_CATEGORIES = {"CARTOON/SQUEAK", "METAL/FRICTION", "RUBBER/FRICTION", "WOOD/FRICTION"}
CRACK_SOUND_CATEGORIES = {"EXPLOSIONS/REAL", "WOOD/BREAK", "ROCKS/IMPACT", "DESIGNED/IMPACT", "ICE/BREAK"}
MUSICAL_RING_CATEGORIES = {"MUSICAL/PERCUSSION", "BELLS/GONG", "METAL/TONAL"}

CSV_COLUMNS = (
    "mode",
    "raw",
    "canonical",
    "kind",
    "slot",
    "existing_canonical_status",
    "approved_for_ai",
    "field_quality",
    "example_quality",
    "category_alignment",
    "qa_flags",
    "review_risk",
    "recommendation",
    "reason",
    "example_summary",
)


@dataclass(frozen=True)
class ReviewSummary:
    total_approved: int
    reviewed_count: int
    allow_prompt_count: int
    alias_only_count: int
    block_count: int
    csv_path: str
    report_path: str
    canonical_tokens_sha256: str
    canonical_tokens_changed: bool
    ai_invoked: bool = False
    promote: bool = False


def review_ai_prompt_candidates(
    evidence_path: Path = DEFAULT_EVIDENCE,
    expanded_path: Path = DEFAULT_EXPANDED,
    prompt_root: Path = DEFAULT_PROMPT_ROOT,
    csv_out: Path = DEFAULT_CSV_OUT,
    report_path: Path = DEFAULT_REPORT,
    canonical_path: Path = DEFAULT_CANONICAL,
) -> ReviewSummary:
    """Review prompt-pack candidates deterministically; never invokes AI."""
    evidence_path = Path(evidence_path)
    expanded_path = Path(expanded_path)
    prompt_root = Path(prompt_root)
    csv_out = Path(csv_out)
    report_path = Path(report_path)
    canonical_path = Path(canonical_path)

    for path in (evidence_path, canonical_path):
        if not path.is_file():
            raise FileNotFoundError(f"Required input not found: {path}")

    canonical_before = _sha256(canonical_path)
    evidence_rows = _load_evidence(evidence_path)
    approved_rows = [row for row in evidence_rows if row.get("approved_for_ai") == "yes"]
    expanded_by_canonical = _load_expanded_examples(expanded_path)

    reviewed: list[dict[str, str]] = []
    for mode in PROMPT_MODES:
        jsonl_path = prompt_root / mode / "alias_prompt_items.jsonl"
        if not jsonl_path.is_file():
            raise FileNotFoundError(f"Required prompt pack not found: {jsonl_path}")
        for item in _load_prompt_items(jsonl_path):
            evidence = _find_evidence(evidence_rows, item)
            expanded = expanded_by_canonical.get(item["canonical"], [])
            reviewed.append(
                _review_item(
                    mode=mode,
                    item=item,
                    evidence=evidence,
                    expanded_examples=expanded,
                )
            )

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(csv_out, reviewed)
    _write_report(
        report_path,
        reviewed=reviewed,
        approved_rows=approved_rows,
        evidence_path=evidence_path,
        expanded_path=expanded_path,
        prompt_root=prompt_root,
        canonical_before=canonical_before,
        canonical_path=canonical_path,
    )

    canonical_after = _sha256(canonical_path)
    if canonical_after != canonical_before:
        raise RuntimeError("canonical_tokens.csv changed while reviewing prompt candidates")

    counts = Counter(row["recommendation"] for row in reviewed)
    return ReviewSummary(
        total_approved=len(approved_rows),
        reviewed_count=len(reviewed),
        allow_prompt_count=counts.get("allow_prompt", 0),
        alias_only_count=counts.get("alias_only", 0),
        block_count=counts.get("block", 0),
        csv_path=str(csv_out),
        report_path=str(report_path),
        canonical_tokens_sha256=canonical_before,
        canonical_tokens_changed=False,
    )


def _review_item(
    *,
    mode: str,
    item: dict[str, object],
    evidence: dict[str, str],
    expanded_examples: list[dict[str, str]],
) -> dict[str, str]:
    canonical = str(item["canonical"])
    raw = evidence.get("raw", canonical.casefold())
    kind = str(item.get("candidate_type") or evidence.get("kind") or "token")
    slot = str(item.get("slot") or evidence.get("slot_guess") or "unknown")
    examples = list(item.get("examples") or [])
    if not examples:
        examples = _parse_evidence_examples(evidence)

    status = evidence.get("existing_canonical_status", "")
    example_quality = evidence.get("example_quality", "")
    category_alignment = evidence.get("category_alignment", "")
    field_quality = evidence.get("field_quality", "")
    qa_flags = evidence.get("qa_flags", "")
    approved_for_ai = evidence.get("approved_for_ai", "no")

    reasons: list[str] = []
    review_flags: list[str] = [flag for flag in qa_flags.split(";") if flag]
    review_risk = _base_review_risk(raw, canonical, kind, review_flags, category_alignment)

    recommendation = "allow_prompt"
    if status == "existing_conflict":
        recommendation = "block"
        reasons.append("existing_conflict")
    elif example_quality == "low":
        recommendation = "block"
        reasons.append("example_quality_low")
    elif category_alignment in {"weak", "unknown"} and not _fx_name_only_metadata_gap(
        evidence, examples, expanded_examples
    ):
        recommendation = "block"
        reasons.append(f"category_alignment_{category_alignment}")
    elif status == "existing_keep":
        recommendation = "alias_only"
        reasons.append("existing_keep")

    recommendation, review_risk, token_reasons, token_flags = _apply_token_rules(
        raw=raw,
        canonical=canonical,
        kind=kind,
        slot=slot,
        mode=mode,
        examples=examples,
        expanded_examples=expanded_examples,
        evidence=evidence,
        base_recommendation=recommendation,
        base_risk=review_risk,
    )
    reasons.extend(token_reasons)
    review_flags.extend(flag for flag in token_flags if flag not in review_flags)

    if mode == "new_candidate" and recommendation == "alias_only":
        reasons.append("not_for_new_candidate")

    reason = ";".join(dict.fromkeys(reasons))
    example_summary = _summarize_examples(examples)
    return {
        "mode": mode,
        "raw": raw,
        "canonical": canonical,
        "kind": kind,
        "slot": slot,
        "existing_canonical_status": status,
        "approved_for_ai": approved_for_ai,
        "field_quality": field_quality,
        "example_quality": example_quality,
        "category_alignment": category_alignment,
        "qa_flags": ";".join(review_flags),
        "review_risk": review_risk,
        "recommendation": recommendation,
        "reason": reason,
        "example_summary": example_summary,
    }


def _apply_token_rules(
    *,
    raw: str,
    canonical: str,
    kind: str,
    slot: str,
    mode: str,
    examples: list[dict[str, str]],
    expanded_examples: list[dict[str, str]],
    evidence: dict[str, str],
    base_recommendation: str,
    base_risk: str,
) -> tuple[str, str, list[str], list[str]]:
    if base_recommendation == "block":
        return base_recommendation, base_risk, [], []

    token = raw.casefold()
    parts = set(token.split())
    reasons: list[str] = []
    flags: list[str] = []
    recommendation = base_recommendation
    review_risk = base_risk

    if parts & HIGH_RISK_TOKENS:
        flags.append("high_risk_token")

    if token == "gun" or canonical == "Gun":
        recommendation, review_risk, gun_reasons, gun_flags = _review_gun(
            examples, expanded_examples, mode, recommendation, review_risk
        )
        reasons.extend(gun_reasons)
        flags.extend(gun_flags)
    elif token == "hit" or canonical == "Hit":
        recommendation, review_risk, hit_reasons, hit_flags = _review_hit(
            examples, evidence, recommendation, review_risk
        )
        reasons.extend(hit_reasons)
        flags.extend(hit_flags)
    elif token == "squeak" or canonical == "Squeak":
        recommendation, review_risk, squeak_reasons, squeak_flags = _review_squeak(
            examples, recommendation, review_risk
        )
        reasons.extend(squeak_reasons)
        flags.extend(squeak_flags)
    elif token == "crack" or canonical == "Crack":
        recommendation, review_risk, crack_reasons, crack_flags = _review_crack(
            examples, recommendation, review_risk
        )
        reasons.extend(crack_reasons)
        flags.extend(crack_flags)
    elif canonical == "Single Shot":
        recommendation, review_risk, shot_reasons, shot_flags = _review_single_shot(
            examples, kind, recommendation, review_risk
        )
        reasons.extend(shot_reasons)
        flags.extend(shot_flags)
    elif token == "ring" or canonical == "Ring":
        recommendation, review_risk, ring_reasons, ring_flags = _review_ring(
            examples, mode, recommendation, review_risk
        )
        reasons.extend(ring_reasons)
        flags.extend(ring_flags)
    elif token == "shot" or canonical == "Shot":
        recommendation, review_risk, shot_reasons, shot_flags = _review_shot_token(
            examples, expanded_examples, recommendation, review_risk
        )
        reasons.extend(shot_reasons)
        flags.extend(shot_flags)

    return recommendation, review_risk, reasons, flags


def _review_gun(
    examples: list[dict[str, str]],
    expanded_examples: list[dict[str, str]],
    mode: str,
    recommendation: str,
    review_risk: str,
) -> tuple[str, str, list[str], list[str]]:
    reasons: list[str] = []
    flags: list[str] = []
    profile = _gun_example_profile(examples, expanded_examples)

    if profile["tool_gun_ratio"] >= 0.5:
        return "block", "high", ["tool_gun_context"], ["tool_gun_context"]

    if profile["firearm_ratio"] >= 0.5 and profile["artillery_ratio"] < 0.34:
        risk = "medium" if profile["artillery_ratio"] else "low"
        if recommendation != "alias_only":
            recommendation = "allow_prompt"
        reasons.append("firearm_context")
        return recommendation, max(review_risk, risk, key=_risk_rank), reasons, flags

    if profile["artillery_ratio"] >= 0.5 or profile["long_gun_ratio"] >= 0.5:
        flags.append("cannon_artillery_context")
        reasons.append("cannon_long_gun_context")
        if mode == "new_candidate":
            recommendation = "alias_only"
        else:
            recommendation = "alias_only"
        return recommendation, "high", reasons, flags

    reasons.append("ambiguous_gun_context")
    return "alias_only", "high", reasons, flags


def _review_hit(
    examples: list[dict[str, str]],
    evidence: dict[str, str],
    recommendation: str,
    review_risk: str,
) -> tuple[str, str, list[str], list[str]]:
    reasons: list[str] = []
    flags = ["ambiguous_with_impact", "ambiguous_with_knock", "ambiguous_with_punch"]
    if _is_description_only_hit(evidence, examples):
        return "block", "high", ["generic_description_hit", "no_fxname_sound_action"], flags

    impact_hits = sum(
        1
        for example in examples
        if _normalize_category(example.get("category", "")) in IMPACT_CATEGORIES
        or "impact" in example.get("fx_name", "").casefold()
        or "hit" in example.get("fx_name", "").casefold()
    )
    if impact_hits >= max(1, len(examples) // 2):
        reasons.extend(flags)
        reasons.append("forbid_visual_alias_命中")
        return "allow_prompt", "high", reasons, flags

    return "block", "high", ["non_sound_design_hit"], flags


def _review_squeak(
    examples: list[dict[str, str]],
    recommendation: str,
    review_risk: str,
) -> tuple[str, str, list[str], list[str]]:
    reasons: list[str] = []
    flags: list[str] = []
    categories = [_normalize_category(example.get("category", "")) for example in examples]
    fx_names = [example.get("fx_name", "") for example in examples]
    positive = sum(
        1
        for category, fx_name in zip(categories, fx_names)
        if category in SQUEAK_POSITIVE_CATEGORIES
        or "squeak" in fx_name.casefold()
        or "toy" in fx_name.casefold()
    )
    guns_miscat = sum(
        1
        for category, fx_name in zip(categories, fx_names)
        if category == "GUNS/CANNON" and "metal squeak" in fx_name.casefold()
    )
    if guns_miscat:
        flags.append("category_metadata_mismatch")
        review_risk = "high" if guns_miscat >= 2 else "medium"
        reasons.append("guns_category_with_metal_squeak_fxname")

    if positive >= max(1, len(examples) // 2):
        reasons.append("toy_cartoon_metal_friction_squeak")
        if recommendation != "alias_only":
            recommendation = "allow_prompt"
        return recommendation, max(review_risk, "medium", key=_risk_rank), reasons, flags

    return "block", "high", ["irrelevant_squeak_categories"], flags


def _review_crack(
    examples: list[dict[str, str]],
    recommendation: str,
    review_risk: str,
) -> tuple[str, str, list[str], list[str]]:
    reasons: list[str] = []
    flags = ["broad_material_spread", "forbid_visual_alias_裂纹"]
    categories = {_normalize_category(example.get("category", "")) for example in examples}
    sound_like = sum(
        1
        for example in examples
        if "crack" in example.get("fx_name", "").casefold()
        or _normalize_category(example.get("category", "")) in CRACK_SOUND_CATEGORIES
    )
    if sound_like >= max(1, len(examples) // 2) and len(categories) >= 2:
        reasons.extend(flags)
        if recommendation != "alias_only":
            recommendation = "allow_prompt"
        risk = "medium" if len(categories) >= 3 else "low"
        return recommendation, max(review_risk, risk, key=_risk_rank), reasons, flags
    return "block", "high", ["unclear_crack_sound_evidence"], flags


def _review_single_shot(
    examples: list[dict[str, str]],
    kind: str,
    recommendation: str,
    review_risk: str,
) -> tuple[str, str, list[str], list[str]]:
    reasons = ["phrase_candidate", "keep_phrase_do_not_split"]
    flags: list[str] = []
    if kind != "phrase":
        return "block", "high", ["phrase_required"], flags

    rifle_hits = sum(
        1
        for example in examples
        if _normalize_category(example.get("category", "")) == "GUNS/RIFLE"
        and "single shot" in example.get("fx_name", "").casefold()
    )
    if rifle_hits >= max(1, len(examples) // 2):
        if recommendation != "alias_only":
            recommendation = "allow_prompt"
        return recommendation, max(review_risk, "medium", key=_risk_rank), reasons, flags
    return "block", "high", ["missing_rifle_single_shot_fxname"], flags


def _review_ring(
    examples: list[dict[str, str]],
    mode: str,
    recommendation: str,
    review_risk: str,
) -> tuple[str, str, list[str], list[str]]:
    reasons: list[str] = []
    flags: list[str] = []
    if any(_is_ambience_ring(example) for example in examples):
        return "block", "high", ["ambience_ring"], ["ambience_ring"]

    musical = sum(
        1
        for example in examples
        if _normalize_category(example.get("category", "")) in MUSICAL_RING_CATEGORIES
        or "ring out" in example.get("fx_name", "").casefold()
    )
    if musical >= max(1, len(examples) // 2):
        reasons.append("musical_percussion_ringing")
        reasons.append("not_for_new_candidate")
        return "alias_only", "medium", reasons, flags

    return "alias_only", "high", ["ambiguous_ring_context"], flags


def _review_shot_token(
    examples: list[dict[str, str]],
    expanded_examples: list[dict[str, str]],
    recommendation: str,
    review_risk: str,
) -> tuple[str, str, list[str], list[str]]:
    reasons: list[str] = []
    flags: list[str] = []
    all_examples = examples + expanded_examples[:6]
    if any(_is_shotgun_microphone(example) for example in all_examples):
        return "block", "high", ["shotgun_microphone"], ["shotgun_microphone"]

    processed = sum(
        1
        for example in examples
        if "sweetener" in example.get("fx_name", "").casefold()
        or "processed" in example.get("description", "").casefold()
    )
    weapon = sum(
        1
        for example in examples
        if _normalize_category(example.get("category", "")) in {"GUNS/CANNON", "GUNS/RIFLE"}
        and "shot" in example.get("fx_name", "").casefold()
    )
    if processed >= max(1, len(examples) // 2):
        flags.append("synthetic_processed_shot")
        review_risk = "medium"
        reasons.append("synthetic_processed_shot")
        recommendation = "alias_only"
        return recommendation, review_risk, reasons, flags

    if weapon >= max(1, len(examples) // 2):
        reasons.append("guns_rifle_or_cannon_shot")
        if recommendation == "allow_prompt":
            recommendation = "alias_only"
        return recommendation, max(review_risk, "medium", key=_risk_rank), reasons, flags

    return recommendation, review_risk, reasons, flags


def _gun_example_profile(
    examples: list[dict[str, str]],
    expanded_examples: list[dict[str, str]],
) -> dict[str, float]:
    sample = examples + expanded_examples[:12]
    if not sample:
        return {
            "tool_gun_ratio": 0.0,
            "artillery_ratio": 0.0,
            "long_gun_ratio": 0.0,
            "firearm_ratio": 0.0,
        }

    tool_gun = artillery = long_gun = firearm = 0
    for example in sample:
        text = _example_text(example)
        category = _normalize_category(example.get("category", ""))
        fx_name = example.get("fx_name", "").casefold()
        if any(marker in text for marker in TOOL_GUN_MARKERS):
            tool_gun += 1
        if any(marker in text for marker in GUN_ARTILLERY_MARKERS) or category == "GUNS/CANNON":
            artillery += 1
        if "long gun" in text or "long gun" in fx_name:
            long_gun += 1
        if category in GUN_WEAPON_CATEGORIES or any(
            term in text for term in ("rifle", "pistol", "firearm", "ak47", "assault rifle")
        ):
            firearm += 1

    total = len(sample)
    return {
        "tool_gun_ratio": tool_gun / total,
        "artillery_ratio": artillery / total,
        "long_gun_ratio": long_gun / total,
        "firearm_ratio": firearm / total,
    }


def _is_description_only_hit(
    evidence: dict[str, str], examples: list[dict[str, str]]
) -> bool:
    flags = {flag for flag in evidence.get("qa_flags", "").split(";") if flag}
    if "generic_description_hit" in flags:
        return True
    if evidence.get("fx_name_hits", "0") != "0":
        return False
    description_hits = int(evidence.get("description_hits") or "0")
    if description_hits <= 0:
        return False
    fxname_examples = sum(1 for example in examples if example.get("fx_name"))
    return fxname_examples < max(1, len(examples) // 2)


def _fx_name_only_metadata_gap(
    evidence: dict[str, str],
    examples: list[dict[str, str]],
    expanded_examples: list[dict[str, str]],
) -> bool:
    if evidence.get("fx_name_hits", "0") == "0":
        return False
    if not examples:
        return False
    fxname_hits = sum(
        1
        for example in examples
        if example.get("fx_name") and _contains_token(evidence.get("raw", ""), example["fx_name"])
    )
    if fxname_hits < max(1, len(examples) // 2):
        return False
    missing_category = sum(
        1 for example in examples if not (example.get("category") or example.get("cat_id"))
    )
    expanded_missing = sum(
        1 for example in expanded_examples[:6] if not (example.get("category") or example.get("cat_id"))
    )
    return missing_category >= 1 or expanded_missing >= 2


def _base_review_risk(
    raw: str,
    canonical: str,
    kind: str,
    qa_flags: list[str],
    category_alignment: str,
) -> str:
    parts = set(raw.casefold().split())
    if "existing_conflict" in qa_flags:
        return "high"
    if parts & HIGH_RISK_TOKENS:
        if category_alignment == "mixed" or "category_mixed" in qa_flags:
            return "high"
        return "medium"
    if category_alignment == "mixed":
        return "medium"
    if kind == "phrase":
        return "medium"
    return "low"


def _summarize_examples(examples: list[dict[str, str]], limit: int = 3) -> str:
    chunks: list[str] = []
    for example in examples[:limit]:
        fx_name = example.get("fx_name", "").strip()
        category = _normalize_category(example.get("category", ""))
        if fx_name and category:
            chunks.append(f"{fx_name} [{category}]")
        elif fx_name:
            chunks.append(fx_name)
    return " | ".join(chunks)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_report(
    path: Path,
    *,
    reviewed: list[dict[str, str]],
    approved_rows: list[dict[str, str]],
    evidence_path: Path,
    expanded_path: Path,
    prompt_root: Path,
    canonical_before: str,
    canonical_path: Path,
) -> None:
    by_mode: dict[str, list[dict[str, str]]] = {mode: [] for mode in PROMPT_MODES}
    for row in reviewed:
        by_mode[row["mode"]].append(row)

    counts = Counter(row["recommendation"] for row in reviewed)
    downgraded = [
        row
        for row in reviewed
        if row["approved_for_ai"] == "yes" and row["recommendation"] != "allow_prompt"
    ]
    keepers = [row for row in reviewed if row["recommendation"] == "allow_prompt"]
    dangerous = sorted(
        [row for row in reviewed if row["review_risk"] == "high" or row["recommendation"] == "block"],
        key=lambda row: (row["review_risk"], row["canonical"], row["mode"]),
        reverse=True,
    )

    lines = [
        "# AI Prompt Candidate Review",
        "",
        "Deterministic machine review before AI alias prompt execution.",
        "",
        f"- total approved_for_ai: `{len(approved_rows)}`",
        f"- reviewed prompt-pack items: `{len(reviewed)}`",
        f"- allow_prompt: `{counts.get('allow_prompt', 0)}`",
        f"- alias_only: `{counts.get('alias_only', 0)}`",
        f"- block: `{counts.get('block', 0)}`",
        "- AI invoked: `no`",
        "- promote: `no`",
        "- canonical_tokens.csv changed: `no`",
        "",
        "## new_candidate conclusions",
        "",
    ]
    lines.extend(_mode_section(by_mode["new_candidate"]))
    lines.extend(["", "## alias_expansion conclusions", ""])
    lines.extend(_mode_section(by_mode["alias_expansion"]))
    lines.extend(
        [
            "",
            "## Downgraded items",
            "",
            *(_bullet_review(row) for row in downgraded),
            "",
            "## Best to keep",
            "",
            *(_bullet_review(row) for row in keepers),
            "",
            "## Most dangerous",
            "",
            *(_bullet_review(row) for row in dangerous),
            "",
            "## Inputs",
            "",
            f"- `{evidence_path}`",
            f"- `{expanded_path}`",
            f"- `{prompt_root / 'new_candidate' / 'alias_prompt_items.jsonl'}`",
            f"- `{prompt_root / 'alias_expansion' / 'alias_prompt_items.jsonl'}`",
            "",
            "## Canonical token guard",
            "",
            f"- canonical_tokens_sha256: `{canonical_before}`",
            f"- canonical path: `{canonical_path}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _mode_section(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return ["- none"]
    return [
        (
            f"- **{row['canonical']}** ({row['kind']}/{row['slot']}): "
            f"risk=`{row['review_risk']}`, recommendation=`{row['recommendation']}`; "
            f"{row['reason'] or 'no extra reason'}"
        )
        for row in rows
    ]


def _bullet_review(row: dict[str, str]) -> str:
    return (
        f"- `{row['mode']}` **{row['canonical']}**: "
        f"recommendation=`{row['recommendation']}`, risk=`{row['review_risk']}`; "
        f"{row['reason']}"
    )


def _load_evidence(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(handle)]


def _find_evidence(rows: list[dict[str, str]], item: dict[str, object]) -> dict[str, str]:
    canonical = str(item["canonical"])
    slot = str(item.get("slot") or "")
    for row in rows:
        if row.get("canonical_guess") == canonical and (
            not slot or row.get("slot_guess") == slot
        ):
            return row
    for row in rows:
        if row.get("canonical_guess") == canonical:
            return row
    return {
        "raw": canonical.casefold(),
        "canonical_guess": canonical,
        "kind": str(item.get("candidate_type") or "token"),
        "slot_guess": slot or "unknown",
        "approved_for_ai": "no",
    }


def _load_expanded_examples(path: Path) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    if not path.is_file():
        return grouped
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            canonical = row.get("canonical_guess") or ""
            grouped.setdefault(canonical, []).append({key: value or "" for key, value in row.items()})
    return grouped


def _load_prompt_items(path: Path) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            items.append(json.loads(line))
    return items


def _parse_evidence_examples(evidence: dict[str, str]) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    for field in ("example_1", "example_2", "example_3"):
        raw = evidence.get(field, "").strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"fx_name": raw, "description": "", "category": "", "cat_id": ""}
        if isinstance(payload, dict):
            examples.append(
                {
                    "fx_name": str(payload.get("fx_name", "")),
                    "description": str(payload.get("description", "")),
                    "category": str(payload.get("category", "")),
                    "cat_id": str(payload.get("cat_id", "")),
                }
            )
    return examples


def _example_text(example: dict[str, str]) -> str:
    return " ".join(
        str(example.get(field, "") or "")
        for field in ("fx_name", "description", "keywords", "filename", "category", "cat_id")
    ).casefold()


def _normalize_category(category: str) -> str:
    category = category.strip()
    if "/" not in category and category:
        return category
    return category


def _contains_token(raw: str, text: str) -> bool:
    return bool(
        re.search(
            r"(?<![a-z0-9])" + re.escape(raw.casefold()) + r"(?![a-z0-9])",
            text.casefold(),
        )
    )


def _is_shotgun_microphone(example: dict[str, str]) -> bool:
    text = _example_text(example)
    return "shotgun microphone" in text or "shotgun mic" in text


def _is_ambience_ring(example: dict[str, str]) -> bool:
    category = example.get("category", "").casefold()
    return category.startswith("ambience") and not example.get("fx_name")


def _risk_rank(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(value, 0)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--expanded", type=Path, default=DEFAULT_EXPANDED)
    parser.add_argument("--prompt-root", type=Path, default=DEFAULT_PROMPT_ROOT)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV_OUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    args = parser.parse_args(argv)
    try:
        summary = review_ai_prompt_candidates(
            args.evidence,
            args.expanded,
            args.prompt_root,
            args.csv_out,
            args.report,
            args.canonical,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    print(
        f"reviewed={summary.reviewed_count} approved={summary.total_approved} "
        f"allow={summary.allow_prompt_count} alias_only={summary.alias_only_count} "
        f"block={summary.block_count} ai_invoked=no promote=no "
        f"canonical_changed={str(summary.canonical_tokens_changed).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
