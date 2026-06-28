#!/usr/bin/env python3
"""BOOM One Mining v0.1 b001 auto promote phase.

Reads promote_ready=true candidates, applies deterministic hard-rule selection
(no external AI / NLLB / free translation), appends keep rows to
canonical_tokens.csv, recomputes after-state metrics, and rolls back the batch
when the after gate is not satisfied.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.boom_one_mining_v0_1_b001 as bo  # noqa: E402
from fxengine.canonical_audit import audit_canonical_csv  # noqa: E402
from fxengine.canonical_db import (  # noqa: E402
    CANONICAL_COLUMNS,
    DEFAULT_CANONICAL_PATH,
    FORBIDDEN_BROAD_ZH_TOKENS,
    load_canonical_rows,
)

PROMOTED_CSV = bo.OUTPUT_DIR / f"{bo.BATCH_ID}_promoted.csv"
REJECTED_CSV = bo.OUTPUT_DIR / f"{bo.BATCH_ID}_rejected.csv"
AFTER_MD = bo.OUTPUT_DIR / f"{bo.BATCH_ID}_after.md"
PROMOTE_METRICS_JSON = bo.OUTPUT_DIR / f"{bo.BATCH_ID}_promote_metrics.json"

# Deterministic curated vocabularies. Generic FXName tokens may auto-promote at
# high confidence; proper nouns are accepted but down-weighted.
GENERIC_OBJECT = (bo.OBJECT_CANONICALS - {"augusta", "boeing"}) | {"engine", "pedals", "window"}
SLOT_BY_CANONICAL: dict[str, str] = {}
for _value in bo.ACTION_CANONICALS | {"turbine rev up", "shut down", "idle"}:
    SLOT_BY_CANONICAL.setdefault(_value, "action")
for _value in bo.MATERIAL_CANONICALS:
    SLOT_BY_CANONICAL[_value] = "material"
for _value in bo.MODIFIER_CANONICALS:
    SLOT_BY_CANONICAL[_value] = "modifier"
for _value in bo.DETAIL_CANONICALS:
    SLOT_BY_CANONICAL[_value] = "detail"
for _value in GENERIC_OBJECT:
    SLOT_BY_CANONICAL[_value] = "object"

PROPER_NOUNS = {
    "boeing",
    "augusta",
    "globemaster",
    "lancer",
    "flanker",
    "stratofortress",
    "maverick",
    "airbus",
    "eurocopter",
    "sikorsky",
    "antonov",
    "lockheed",
    "hercules",
    "chinook",
    "apache",
    "raptor",
    "hornet",
    "viper",
    "mustang",
    "spitfire",
}

# Canonicals that are too ambiguous for unattended promotion. They must go
# through human review instead (aligns with AI_ALIAS_REVIEW_RULES.md).
HIGH_RISK_CANONICALS = {
    "hit",
    "ring",
    "shot",
    "single shot",
    "gun",
    "crack",
    "drop",
    "roll",
    "break",
    "bang",
    "fire",
    "body",
    "knock",
    "punch",
}
ROMAN_NUMERALS = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}

PRIORITY_BY_SLOT = {
    "material": 95,
    "object": 95,
    "source": 95,
    "modifier": 92,
    "detail": 92,
    "action": 90,
}
AMBIGUITY_BY_SLOT = {
    "material": "low",
    "object": "low",
    "source": "low",
    "modifier": "low",
    "detail": "low",
    "action": "medium",
}


@dataclass
class Selection:
    raw: str
    canonical: str
    lang: str
    slot: str
    priority: int
    rule_type: str
    ambiguity: str
    tags: str
    promote_class: str
    frequency: int
    evidence_rows: list[int] = field(default_factory=list)
    en_examples: list[str] = field(default_factory=list)


@dataclass
class Rejection:
    raw: str
    canonical: str
    lang: str
    slot: str
    frequency: int
    reason: str
    sample_row: int
    en_fxname: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_candidates(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _existing_keep_keys() -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for token in load_canonical_rows(DEFAULT_CANONICAL_PATH):
        if token.review_status == "keep":
            keys.add((token.lang, token.raw.casefold()))
    return keys


def _existing_canonical_by_raw() -> dict[tuple[str, str], dict[str, object]]:
    table: dict[tuple[str, str], dict[str, object]] = {}
    for token in load_canonical_rows(DEFAULT_CANONICAL_PATH):
        key = (token.lang, token.raw.casefold())
        entry = table.setdefault(key, {"canonicals": set(), "has_keep": False})
        entry["canonicals"].add(token.canonical.casefold())
        if token.review_status == "keep":
            entry["has_keep"] = True
    return table


def _is_ascii(text: str) -> bool:
    return text.isascii() and any(ch.isalpha() for ch in text)


def _reject_token_reason(raw: str, canonical: str, slot: str) -> str | None:
    if not raw.strip() or not canonical.strip():
        return "missing_raw_or_canonical"
    if raw in FORBIDDEN_BROAD_ZH_TOKENS:
        return "forbidden_broad_token"
    if bo._has_zh(raw) and len(raw) == 1:
        return "single_char_zh"
    if _is_ascii(raw):
        compact = raw.strip()
        if compact.casefold() in ROMAN_NUMERALS:
            return "roman_numeral_metadata"
        if len(compact.replace(" ", "")) < 3:
            return "too_short_token"
    if raw.strip().isdigit():
        return "numeric_metadata"
    return None


def _classify(canonical: str) -> tuple[str, str] | None:
    """Return (promote_class, slot) or None when not auto-promotable."""
    normalized = " ".join(bo._target_tokens(canonical)) or canonical.strip().lower()
    full = canonical.strip().lower()
    if full in HIGH_RISK_CANONICALS or normalized in HIGH_RISK_CANONICALS:
        return None
    if full in PROPER_NOUNS or normalized in PROPER_NOUNS:
        return "proper_noun", "source"
    slot = SLOT_BY_CANONICAL.get(full) or SLOT_BY_CANONICAL.get(normalized)
    if slot:
        return "generic", slot
    return None


def select(
    candidates: Sequence[dict[str, str]],
    existing_keep: set[tuple[str, str]],
) -> tuple[list[Selection], list[Rejection]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        if row.get("promote_ready", "").strip().lower() != "true":
            continue
        if row.get("skip_reason", "").strip():
            continue
        if row.get("candidate_status", "").strip() != "promote_ready":
            continue
        raw = row.get("suggested_raw", "").strip()
        if not raw:
            continue
        grouped[(row.get("lang", "").strip(), raw.casefold())].append(row)

    selections: list[Selection] = []
    rejections: list[Rejection] = []
    for (lang, _rawcf), rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        canonicals = {row["suggested_canonical"].strip() for row in rows}
        raw = rows[0]["suggested_raw"].strip()
        canonical = rows[0]["suggested_canonical"].strip()
        slot_in = rows[0].get("slot", "").strip()
        sample_row = int(rows[0]["row_number"])
        en_examples = []
        for row in rows:
            if row["en_fxname"] not in en_examples:
                en_examples.append(row["en_fxname"])
        frequency = len(rows)

        if len(canonicals) > 1:
            rejections.append(
                Rejection(raw, " | ".join(sorted(canonicals)), lang, slot_in, frequency,
                          "in_batch_conflict", sample_row, rows[0]["en_fxname"])
            )
            continue
        if (lang, raw.casefold()) in existing_keep:
            rejections.append(
                Rejection(raw, canonical, lang, slot_in, frequency,
                          "already_keep_in_canonical", sample_row, rows[0]["en_fxname"])
            )
            continue
        token_reason = _reject_token_reason(raw, canonical, slot_in)
        if token_reason:
            rejections.append(
                Rejection(raw, canonical, lang, slot_in, frequency, token_reason, sample_row, rows[0]["en_fxname"])
            )
            continue
        classification = _classify(canonical)
        if classification is None:
            rejections.append(
                Rejection(raw, canonical, lang, slot_in, frequency,
                          "not_in_curated_vocab_or_high_risk", sample_row, rows[0]["en_fxname"])
            )
            continue
        promote_class, slot = classification
        if slot == "unknown":
            rejections.append(
                Rejection(raw, canonical, lang, slot_in, frequency, "slot_unknown", sample_row, rows[0]["en_fxname"])
            )
            continue
        if promote_class == "proper_noun":
            priority = 75
            ambiguity = "medium"
            tags = "boom/proper_noun/aircraft"
        else:
            priority = PRIORITY_BY_SLOT.get(slot, 90)
            ambiguity = AMBIGUITY_BY_SLOT.get(slot, "low")
            tags = f"boom/{slot}"
        selections.append(
            Selection(
                raw=raw,
                canonical=canonical,
                lang=lang,
                slot=slot,
                priority=priority,
                rule_type="phrase",
                ambiguity=ambiguity,
                tags=tags,
                promote_class=promote_class,
                frequency=frequency,
                evidence_rows=[int(row["row_number"]) for row in rows[:5]],
                en_examples=en_examples[:3],
            )
        )
    selections.sort(key=lambda item: (-item.frequency, item.lang, item.raw))
    return selections, rejections


def _canonical_row(selection: Selection) -> list[str]:
    values = {
        "raw": selection.raw,
        "canonical": selection.canonical,
        "slot": selection.slot,
        "lang": selection.lang,
        "priority": str(selection.priority),
        "rule_type": selection.rule_type,
        "review_status": "keep",
        "ambiguity": selection.ambiguity,
        "tags": selection.tags,
        "source": bo.SOURCE,
        "note": bo.NOTE,
    }
    return [values[column] for column in CANONICAL_COLUMNS]


def append_canonical(path: Path, selections: Sequence[Selection]) -> None:
    """Append keep rows byte-for-byte, preserving the original file's bytes,
    BOM and newline style so the diff only contains the appended lines."""
    original = path.read_bytes()
    newline = b"\r\n" if b"\r\n" in original else b"\n"
    suffix = b"" if (not original or original.endswith(newline)) else newline
    rows: list[bytes] = []
    for selection in selections:
        buffer: list[str] = []
        writer = csv.writer(_StringSink(buffer), lineterminator="")
        writer.writerow(_canonical_row(selection))
        rows.append(buffer[0].encode("utf-8") + newline)
    path.write_bytes(original + suffix + b"".join(rows))


class _StringSink:
    def __init__(self, sink: list[str]) -> None:
        self._sink = sink

    def write(self, value: str) -> int:
        self._sink.append(value)
        return len(value)


def compute_state(pairs, alignment, limit: int) -> tuple[list, dict]:
    analyses, candidates = bo.analyze(pairs)
    sha = _sha256(DEFAULT_CANONICAL_PATH)
    metrics = bo._metrics(analyses, candidates, alignment, sha, sha, limit)
    return analyses, metrics


def _status_by_row(analyses) -> dict[int, object]:
    return {analysis.pair.row_number: analysis for analysis in analyses}


def _delta(before: dict, after: dict) -> dict[str, int]:
    return {key: after[key] - before[key] for key in ("pass", "partial", "needs_review", "unknown", "safety_fail", "conflict")}


def _gate(
    before: dict,
    after: dict,
    *,
    audit_conflict_count: int,
    audit_error_count: int,
    promotion_conflicts: int,
) -> tuple[bool, dict[str, bool]]:
    # NOTE: ``after["conflict"]`` is a candidate-diagnostic count (e.g. 飞越 ->
    # Flyby clashing with an existing canonical). It is inherent to the mining
    # diagnostics and is intentionally NOT a gate signal. The gate instead
    # checks conflicts actually introduced into runtime canonical.
    checks = {
        "safety_fail_zero": after["safety_fail"] == 0,
        "runtime_conflict_zero": audit_conflict_count == 0
        and audit_error_count == 0
        and promotion_conflicts == 0,
        "pass_improved": after["pass"] > before["pass"],
        "unknown_or_needs_review_dropped": (after["unknown"] < before["unknown"])
        or (after["needs_review"] < before["needs_review"]),
    }
    return all(checks.values()), checks


def _write_promoted(path: Path, selections: Sequence[Selection]) -> None:
    columns = (
        "raw", "canonical", "slot", "lang", "priority", "rule_type",
        "review_status", "ambiguity", "tags", "source", "note",
        "promote_class", "frequency", "evidence_rows", "en_examples",
    )
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for s in selections:
            writer.writerow({
                "raw": s.raw, "canonical": s.canonical, "slot": s.slot, "lang": s.lang,
                "priority": s.priority, "rule_type": s.rule_type, "review_status": "keep",
                "ambiguity": s.ambiguity, "tags": s.tags, "source": bo.SOURCE, "note": bo.NOTE,
                "promote_class": s.promote_class, "frequency": s.frequency,
                "evidence_rows": ";".join(str(r) for r in s.evidence_rows),
                "en_examples": " || ".join(s.en_examples),
            })


def _write_rejected(path: Path, rejections: Sequence[Rejection]) -> None:
    columns = ("raw", "canonical", "lang", "slot", "frequency", "reject_reason", "sample_row", "en_fxname")
    ordered = sorted(rejections, key=lambda r: (-r.frequency, r.reason, r.raw))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for r in ordered:
            writer.writerow({
                "raw": r.raw, "canonical": r.canonical, "lang": r.lang, "slot": r.slot,
                "frequency": r.frequency, "reject_reason": r.reason,
                "sample_row": r.sample_row, "en_fxname": r.en_fxname,
            })


def _fix_samples(before_analyses, after_analyses, limit: int = 20) -> list[dict[str, object]]:
    before_map = _status_by_row(before_analyses)
    out: list[dict[str, object]] = []
    for after in after_analyses:
        before = before_map.get(after.pair.row_number)
        if before is None:
            continue
        if before.primary_status != "pass" and after.primary_status == "pass":
            out.append({
                "row": after.pair.row_number,
                "zh": after.pair.zh_fxname,
                "before_out": before.output_fxname,
                "after_out": after.output_fxname,
                "en": after.pair.en_fxname,
            })
        if len(out) >= limit:
            break
    return out


def _remaining_unknowns(after_analyses, limit: int = 20) -> list[tuple[str, int]]:
    counter = Counter(raw for analysis in after_analyses for raw in analysis.unknowns)
    return counter.most_common(limit)


def write_after_report(
    path: Path,
    *,
    before: dict,
    after: dict,
    delta: dict,
    gate_passed: bool,
    gate_checks: dict,
    rolled_back: bool,
    selections: Sequence[Selection],
    rejections: Sequence[Rejection],
    fix_samples: Sequence[dict],
    remaining_unknowns: Sequence[tuple[str, int]],
    sha_before: str,
    sha_after: str,
    after_analyses,
) -> None:
    safety_rows = [a for a in after_analyses if a.safety_issues]
    conflict_rows = [a for a in after_analyses if a.existing_canonical_conflict or a.in_batch_conflict]
    lines = [
        "# BOOM One Mining v0.1 b001 After Report",
        "",
        "## Batch",
        "",
        f"- batch: `{bo.BATCH}`",
        f"- source: `{bo.SOURCE}`",
        f"- note: `{bo.NOTE}`",
        "- phase: `auto_promote`",
        f"- promoted rows: `{len(selections)}`",
        f"- rejected (from promote_ready pool): `{len(rejections)}`",
        f"- rolled_back: `{str(rolled_back).lower()}`",
        "- AI invoked: `no` (deterministic curated rules; no NLLB / free translation)",
        f"- promote: `{'no (rolled back)' if rolled_back else 'yes'}`",
        f"- canonical changed: `{'no' if rolled_back else 'yes'}`",
        "",
        "## Canonical Guard",
        "",
        f"- sha256 before: `{sha_before}`",
        f"- sha256 after: `{sha_after}`",
        f"- changed: `{'no' if sha_before == sha_after else 'yes'}`",
        "",
        "## Before vs After",
        "",
        "| metric | before | after | delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key in ("pass", "partial", "needs_review", "unknown", "safety_fail", "conflict"):
        label = f"{key} (candidate diagnostic)" if key == "conflict" else key
        lines.append(f"| {label} | {before[key]} | {after[key]} | {delta[key]:+d} |")
    lines.extend([
        "",
        "## After Gate",
        "",
        "Note: the `conflict` row above is a candidate-diagnostic count (a proposed",
        "alias clashing with an existing canonical, e.g. 飞越 -> Flyby). It is part of",
        "the mining diagnostics and is NOT a gate signal. The gate uses runtime",
        "canonical audit conflicts + promotion-induced conflicts instead.",
        "",
        f"- gate passed: `{str(gate_passed).lower()}`",
    ])
    for key, value in gate_checks.items():
        lines.append(f"- {key}: `{str(value).lower()}`")

    lines.extend(["", "## Safety Fail Details (after)", ""])
    if not safety_rows:
        lines.append("- none")
    else:
        lines.append("| row | zh_fxname | issues |")
        lines.append("| ---: | --- | --- |")
        for a in safety_rows[:50]:
            lines.append(f"| {a.pair.row_number} | {bo._md(a.pair.zh_fxname)} | {bo._md(';'.join(a.safety_issues))} |")

    lines.extend(["", "## Candidate Diagnostic Conflicts (after, not a gate signal)", ""])
    if not conflict_rows:
        lines.append("- none")
    else:
        lines.append("| row | zh_fxname | en_fxname |")
        lines.append("| ---: | --- | --- |")
        for a in conflict_rows[:50]:
            lines.append(f"| {a.pair.row_number} | {bo._md(a.pair.zh_fxname)} | {bo._md(a.pair.en_fxname)} |")

    lines.extend([
        "",
        "## Forbidden Broad Check",
        "",
        f"- passed: `{str(not any(s.raw in FORBIDDEN_BROAD_ZH_TOKENS for s in selections)).lower()}`",
        "",
        "## Single Char Keep Check",
        "",
        f"- passed: `{str(not any(bo._has_zh(s.raw) and len(s.raw) == 1 for s in selections)).lower()}`",
        "",
        "## Promoted Top 50",
        "",
        "| raw | canonical | slot | lang | priority | class | freq |",
        "| --- | --- | --- | --- | ---: | --- | ---: |",
    ])
    for s in selections[:50]:
        lines.append(
            f"| {bo._md(s.raw)} | {bo._md(s.canonical)} | {s.slot} | {s.lang} | {s.priority} | {s.promote_class} | {s.frequency} |"
        )

    lines.extend(["", "## Rejected Top 50 (with reason)", "", "| raw | canonical | lang | reason | freq |", "| --- | --- | --- | --- | ---: |"])
    for r in sorted(rejections, key=lambda r: (-r.frequency, r.reason, r.raw))[:50]:
        lines.append(f"| {bo._md(r.raw)} | {bo._md(r.canonical)} | {r.lang} | {r.reason} | {r.frequency} |")

    lines.extend(["", "## Top 20 Fix Samples (needs_review/unknown -> pass)", "", "| row | zh_fxname | before | after | en_fxname |", "| ---: | --- | --- | --- | --- |"])
    for sample in fix_samples:
        lines.append(
            f"| {sample['row']} | {bo._md(sample['zh'])} | {bo._md(sample['before_out'])} | {bo._md(sample['after_out'])} | {bo._md(sample['en'])} |"
        )

    lines.extend(["", "## Top 20 Remaining Unknown (after)", "", "| unknown | count |", "| --- | ---: |"])
    for raw, count in remaining_unknowns:
        lines.append(f"| {bo._md(raw)} | {count} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    bo.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pairs, alignment = bo.load_pairs(args.zh_xlsx, args.en_xlsx, args.limit)

    sha_before = _sha256(DEFAULT_CANONICAL_PATH)
    original_bytes = DEFAULT_CANONICAL_PATH.read_bytes()

    before_analyses, before_metrics = compute_state(pairs, alignment, args.limit)
    before = before_metrics["before"]

    candidates = _read_candidates(args.candidates_csv)
    existing_all = _existing_canonical_by_raw()
    existing_keep = {key for key, canon in existing_all.items() if canon["has_keep"]}
    selections, rejections = select(candidates, existing_keep)

    append_canonical(DEFAULT_CANONICAL_PATH, selections)
    try:
        load_canonical_rows(DEFAULT_CANONICAL_PATH)
    except Exception as exc:  # pragma: no cover - safety restore path
        DEFAULT_CANONICAL_PATH.write_bytes(original_bytes)
        raise RuntimeError(f"canonical validation failed after append: {exc}") from exc
    sha_after = _sha256(DEFAULT_CANONICAL_PATH)

    audit = audit_canonical_csv(DEFAULT_CANONICAL_PATH)
    promotion_conflicts = sum(
        1
        for s in selections
        if (s.lang, s.raw.casefold()) in existing_all
        and s.canonical.casefold() not in existing_all[(s.lang, s.raw.casefold())]["canonicals"]
    )

    after_analyses, after_metrics = compute_state(pairs, alignment, args.limit)
    after = after_metrics["before"]

    gate_passed, gate_checks = _gate(
        before,
        after,
        audit_conflict_count=audit.conflict_count,
        audit_error_count=audit.error_count,
        promotion_conflicts=promotion_conflicts,
    )
    rolled_back = not gate_passed
    if rolled_back:
        DEFAULT_CANONICAL_PATH.write_bytes(original_bytes)
        sha_after = _sha256(DEFAULT_CANONICAL_PATH)
        after_analyses, after_metrics = compute_state(pairs, alignment, args.limit)
        after = after_metrics["before"]

    delta = _delta(before, after)
    fix_samples = _fix_samples(before_analyses, after_analyses) if not rolled_back else []
    remaining_unknowns = _remaining_unknowns(after_analyses)

    _write_promoted(PROMOTED_CSV, selections)
    _write_rejected(REJECTED_CSV, rejections)
    write_after_report(
        AFTER_MD,
        before=before,
        after=after,
        delta=delta,
        gate_passed=gate_passed,
        gate_checks=gate_checks,
        rolled_back=rolled_back,
        selections=selections,
        rejections=rejections,
        fix_samples=fix_samples,
        remaining_unknowns=remaining_unknowns,
        sha_before=sha_before,
        sha_after=sha_after,
        after_analyses=after_analyses,
    )

    promote_metrics = {
        "batch": bo.BATCH,
        "source": bo.SOURCE,
        "note": bo.NOTE,
        "canonical_sha256_before": sha_before,
        "canonical_sha256_after": sha_after,
        "canonical_changed": sha_before != sha_after,
        "rolled_back": rolled_back,
        "promoted_count": 0 if rolled_back else len(selections),
        "selected_count": len(selections),
        "rejected_count": len(rejections),
        "proper_noun_count": sum(s.promote_class == "proper_noun" for s in selections),
        "slot_distribution": dict(sorted(Counter(s.slot for s in selections).items())),
        "before": before,
        "after": after,
        "delta": delta,
        "gate_passed": gate_passed,
        "gate_checks": gate_checks,
        "audit_conflict_count": audit.conflict_count,
        "audit_error_count": audit.error_count,
        "promotion_conflicts": promotion_conflicts,
        "forbidden_broad_check": {
            "passed": not any(s.raw in FORBIDDEN_BROAD_ZH_TOKENS for s in selections),
        },
        "single_char_keep_check": {
            "passed": not any(bo._has_zh(s.raw) and len(s.raw) == 1 for s in selections),
        },
        "ai_invoked": False,
        "promote": not rolled_back,
    }
    PROMOTE_METRICS_JSON.write_text(json.dumps(promote_metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        " ".join([
            f"batch={bo.BATCH}",
            f"selected={len(selections)}",
            f"promoted={'0' if rolled_back else len(selections)}",
            f"rejected={len(rejections)}",
            f"rolled_back={'true' if rolled_back else 'false'}",
            f"canonical_changed={'true' if sha_before != sha_after else 'false'}",
            f"pass={before['pass']}->{after['pass']}",
            f"unknown={before['unknown']}->{after['unknown']}",
            f"needs_review={before['needs_review']}->{after['needs_review']}",
            f"safety_fail={after['safety_fail']}",
            f"conflict={after['conflict']}",
            f"gate_passed={'true' if gate_passed else 'false'}",
        ])
    )
    return 0 if gate_passed else 1


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zh-xlsx", type=Path, default=bo.ZH_XLSX)
    parser.add_argument("--en-xlsx", type=Path, default=bo.EN_XLSX)
    parser.add_argument("--limit", type=int, default=bo.DEFAULT_LIMIT)
    parser.add_argument("--candidates-csv", type=Path, default=bo.CANDIDATES_CSV)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
