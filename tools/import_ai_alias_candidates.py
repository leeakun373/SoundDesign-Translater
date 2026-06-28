#!/usr/bin/env python3
"""Import or dry-run generate AI alias candidates for manual review only."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fxengine.canonical_db import (  # noqa: E402
    CANONICAL_COLUMNS,
    DEFAULT_CANONICAL_PATH,
    load_canonical_rows,
)

DEFAULT_NEW_CANDIDATE_PACK = (
    ROOT / "exports" / "ai_alias_prompt_pack" / "reviewed_new_candidate" / "alias_prompt_items.jsonl"
)
DEFAULT_ALIAS_EXPANSION_PACK = (
    ROOT
    / "exports"
    / "ai_alias_prompt_pack"
    / "reviewed_alias_expansion"
    / "alias_prompt_items.jsonl"
)
DEFAULT_OUTPUT_CSV = (
    ROOT / "exports" / "ai_alias_prompt_pack" / "ai_alias_candidates_review_real.csv"
)
DEFAULT_REPORT = ROOT / "reports" / "ai_alias_candidates_review_real_report.md"

PACK_MODES = ("new_candidate", "alias_expansion")
REQUIRED_IMPORT_COLUMNS = {"raw", "canonical", "slot"}
FORBIDDEN_RAW_BY_CANONICAL = {
    "Hit": ("命中",),
    "Crack": ("裂纹",),
}
FORBIDDEN_SHOT_MARKERS = (
    "shotgun microphone",
    "shotgun mic",
    "霰弹麦",
    "散弹麦",
    "枪式麦",
    "麦克风",
)
MIN_ALIASES_PER_CANONICAL = 3
MAX_ALIASES_PER_CANONICAL = 5

AliasGenerator = Callable[[dict[str, object], str], list[dict[str, str]]]

DRY_RUN_MOCK_ALIASES: dict[str, dict[str, list[str]]] = {
    "new_candidate": {
        "Hit": ["打击", "击打", "碰击", "击中"],
        "Squeak": ["吱声", "吱吱", "挤压吱声", "金属吱"],
        "Crack": ["爆裂声", "劈裂", "断裂", "脆响"],
        "Single Shot": ["单发", "单发射击", "单次射击", "一发"],
    },
    "alias_expansion": {
        "Impact": ["冲击", "碰击", "碰击声"],
        "Friction": ["摩擦音", "擦蹭声", "磨蹭"],
        "Gun": ["枪械", "枪支", "长炮", "火炮"],
        "Hit": ["打击", "击打", "碰击", "击中"],
        "Squeak": ["吱声", "吱吱", "挤压吱声", "金属吱"],
        "Shot": ["枪声", "炮击", "开火声", "发射声"],
        "Chain": ["铁链", "链响", "锁链声"],
        "Crack": ["爆裂声", "劈裂", "断裂", "脆响"],
        "Door": ["开门", "关门", "门响"],
        "Drop": ["坠落", "落地声", "坠地"],
        "Ring": ["振铃", "余响", "回响"],
        "Single Shot": ["单发", "单发射击", "单次射击", "一发"],
    },
}


@dataclass(frozen=True)
class ImportSummary:
    input_count: int
    candidate_count: int
    canonical_count: int
    counts_by_canonical: dict[str, int]
    counts_by_pack: dict[str, int]
    csv_path: str
    report_path: str
    rejected_count: int
    rejection_reason_counts: dict[str, int]
    canonical_tokens_sha256_before: str
    canonical_tokens_sha256_after: str
    canonical_tokens_changed: bool
    has_keep: bool
    all_source_ai_candidate: bool
    all_priority_zero: bool
    gun_only_alias_expansion: bool
    ai_invoked: bool = False
    promote: bool = False
    dry_run: bool = True


def import_ai_alias_candidates(
    new_candidate_pack: Path = DEFAULT_NEW_CANDIDATE_PACK,
    alias_expansion_pack: Path = DEFAULT_ALIAS_EXPANSION_PACK,
    output_csv: Path = DEFAULT_OUTPUT_CSV,
    report_path: Path = DEFAULT_REPORT,
    canonical_path: Path = DEFAULT_CANONICAL_PATH,
    *,
    import_csv: Path | None = None,
    generator: AliasGenerator | None = None,
    dry_run: bool = True,
) -> ImportSummary:
    """Validate and write AI alias candidates; never promotes or edits canonical CSV."""
    new_candidate_pack = Path(new_candidate_pack)
    alias_expansion_pack = Path(alias_expansion_pack)
    output_csv = Path(output_csv)
    report_path = Path(report_path)
    canonical_path = Path(canonical_path)
    import_csv = Path(import_csv) if import_csv else None

    for path in (new_candidate_pack, alias_expansion_pack, canonical_path):
        if not path.is_file():
            raise FileNotFoundError(f"Required input not found: {path}")
    _require_reviewed_prompt_pack(new_candidate_pack, "reviewed_new_candidate")
    _require_reviewed_prompt_pack(alias_expansion_pack, "reviewed_alias_expansion")

    canonical_before = _sha256(canonical_path)
    existing_raws = _existing_raw_keys(canonical_path)
    generator = generator or dry_run_mock_alias_generator

    pack_specs = (
        ("new_candidate", new_candidate_pack, _load_prompt_items(new_candidate_pack)),
        ("alias_expansion", alias_expansion_pack, _load_prompt_items(alias_expansion_pack)),
    )
    if import_csv:
        imported_rows = _read_import_rows(import_csv)
        input_count = len(imported_rows)
        accepted, rejection_counts = _import_real_rows(
            imported_rows,
            pack_specs=pack_specs,
            existing_raws=existing_raws,
        )
    else:
        input_count, accepted, rejection_counts = _generate_dry_run_rows(
            pack_specs=pack_specs,
            generator=generator,
            existing_raws=existing_raws,
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(output_csv, accepted)
    counts_by_canonical = dict(sorted(Counter(row["canonical"] for row in accepted).items()))
    counts_by_pack = dict(sorted(Counter(_pack_from_note(row["note"]) for row in accepted).items()))
    if import_csv and len(accepted) + sum(rejection_counts.values()) != input_count:
        raise RuntimeError("real import accounting mismatch")
    canonical_after = _sha256(canonical_path)
    summary = ImportSummary(
        input_count=input_count,
        candidate_count=len(accepted),
        canonical_count=len(counts_by_canonical),
        counts_by_canonical=counts_by_canonical,
        counts_by_pack=counts_by_pack,
        csv_path=str(output_csv),
        report_path=str(report_path),
        rejected_count=sum(rejection_counts.values()),
        rejection_reason_counts=dict(sorted(rejection_counts.items())),
        canonical_tokens_sha256_before=canonical_before,
        canonical_tokens_sha256_after=canonical_after,
        canonical_tokens_changed=canonical_after != canonical_before,
        has_keep=any(row["review_status"] == "keep" for row in accepted),
        all_source_ai_candidate=all(row["source"] == "ai_candidate" for row in accepted),
        all_priority_zero=all(row["priority"] == "0" for row in accepted),
        gun_only_alias_expansion=_gun_only_alias_expansion(accepted),
        dry_run=import_csv is None,
    )
    if summary.canonical_tokens_sha256_after != canonical_before:
        raise RuntimeError("canonical_tokens.csv changed while importing AI alias candidates")
    _write_report(
        report_path,
        summary=summary,
        pack_specs=tuple((mode, path) for mode, path, _items in pack_specs),
        import_csv=import_csv,
    )
    return summary


def dry_run_mock_alias_generator(item: dict[str, object], pack_mode: str) -> list[dict[str, str]]:
    canonical = str(item["canonical"])
    slot = str(item.get("slot") or "unknown")
    templates = DRY_RUN_MOCK_ALIASES.get(pack_mode, {}).get(canonical, [])
    rows: list[dict[str, str]] = []
    for raw in templates[:MAX_ALIASES_PER_CANONICAL]:
        rows.append(
            {
                "raw": raw,
                "canonical": canonical,
                "slot": slot,
                "lang": "zh",
                "priority": "0",
                "rule_type": "alias",
                "review_status": "review",
                "ambiguity": _default_ambiguity(canonical),
                "tags": _default_tags(canonical, slot),
                "source": "ai_candidate",
                "note": f"dry_run_v0.1;pack={pack_mode}",
            }
        )
    return rows


def _generate_dry_run_rows(
    *,
    pack_specs: tuple[tuple[str, Path, list[dict[str, object]]], ...],
    generator: AliasGenerator,
    existing_raws: set[str],
) -> tuple[int, list[dict[str, str]], Counter[str]]:
    input_count = 0
    accepted: list[dict[str, str]] = []
    rejection_counts: Counter[str] = Counter()
    seen_keys: set[tuple[str, str, str]] = set()

    for pack_mode, _pack_path, items in pack_specs:
        for item in items:
            canonical = str(item["canonical"])
            if pack_mode == "new_candidate" and canonical.casefold() == "gun":
                rejection_counts["gun_not_allowed_new_candidate"] += 1
                continue
            proposals = generator(item, pack_mode)
            input_count += len(proposals)
            item_rows, rejections = _normalize_and_filter_rows(
                proposals,
                item=item,
                pack_mode=pack_mode,
                existing_raws=existing_raws,
                seen_keys=seen_keys,
            )
            accepted.extend(item_rows)
            rejection_counts.update(rejections)
    return input_count, accepted, rejection_counts


def _import_real_rows(
    imported_rows: list[dict[str, str]],
    *,
    pack_specs: tuple[tuple[str, Path, list[dict[str, object]]], ...],
    existing_raws: set[str],
) -> tuple[list[dict[str, str]], Counter[str]]:
    reviewed_items: dict[str, dict[tuple[str, str], dict[str, object]]] = {
        mode: {
            (str(item.get("canonical", "")).casefold(), str(item.get("slot", "")).casefold()): item
            for item in items
        }
        for mode, _path, items in pack_specs
    }
    accepted: list[dict[str, str]] = []
    rejection_counts: Counter[str] = Counter()
    seen_keys: set[tuple[str, str, str]] = set()

    for proposal in imported_rows:
        resolved, reason = _resolve_reviewed_item(proposal, reviewed_items)
        if reason:
            rejection_counts[reason] += 1
            continue
        assert resolved is not None
        pack_mode, item = resolved
        row = _normalize_row(
            proposal,
            canonical=str(item["canonical"]),
            slot=str(item.get("slot") or "unknown"),
            pack_mode=pack_mode,
            real_import=True,
        )
        reason = _reject_reason(
            row,
            candidate_type=str(item.get("candidate_type") or "token"),
            pack_mode=pack_mode,
            source_context=proposal.get("source_note", ""),
        )
        if reason:
            rejection_counts[reason] += 1
            continue
        dedupe_key = (row["raw"].casefold(), row["canonical"].casefold(), row["slot"])
        if dedupe_key in seen_keys:
            rejection_counts["duplicate_raw_canonical_slot"] += 1
            continue
        if row["raw"].casefold() in existing_raws:
            rejection_counts["duplicate_existing_canonical_raw"] += 1
            continue
        seen_keys.add(dedupe_key)
        accepted.append(row)

    return accepted, rejection_counts


def _resolve_reviewed_item(
    proposal: Mapping[str, str],
    reviewed_items: Mapping[str, Mapping[tuple[str, str], dict[str, object]]],
) -> tuple[tuple[str, dict[str, object]] | None, str | None]:
    raw = (proposal.get("raw") or "").strip()
    canonical = (proposal.get("canonical") or "").strip()
    slot = (proposal.get("slot") or "").strip().casefold()
    source_note = proposal.get("source_note", "") or ""
    if not raw:
        return None, "missing_raw"
    if not canonical:
        return None, "missing_canonical"
    if not slot:
        return None, "missing_slot"

    pack_hints = {mode for mode in PACK_MODES if mode in source_note.casefold()}
    if len(pack_hints) > 1:
        return None, "multiple_prompt_pack_sources"
    if canonical.casefold() == "gun" and "new_candidate" in pack_hints:
        return None, "gun_not_allowed_new_candidate"

    key = (canonical.casefold(), slot)
    available = [
        (mode, items[key])
        for mode, items in reviewed_items.items()
        if key in items
    ]
    if pack_hints:
        hinted_mode = next(iter(pack_hints))
        for mode, item in available:
            if mode == hinted_mode:
                return (mode, item), None
        return None, "candidate_not_in_reviewed_prompt_pack"
    if len(available) == 1:
        return available[0], None
    if len(available) > 1:
        return None, "ambiguous_prompt_pack_source"
    return None, "candidate_not_in_reviewed_prompt_pack"


def _normalize_and_filter_rows(
    proposals: Iterable[dict[str, str]],
    *,
    item: dict[str, object],
    pack_mode: str,
    existing_raws: set[str],
    seen_keys: set[tuple[str, str, str]],
) -> tuple[list[dict[str, str]], Counter[str]]:
    canonical = str(item["canonical"])
    slot = str(item.get("slot") or "unknown")
    candidate_type = str(item.get("candidate_type") or "token")
    accepted: list[dict[str, str]] = []
    rejections: Counter[str] = Counter()

    for proposal in proposals:
        row = _normalize_row(proposal, canonical=canonical, slot=slot, pack_mode=pack_mode)
        reason = _reject_reason(row, candidate_type=candidate_type, pack_mode=pack_mode)
        if reason:
            rejections[reason] += 1
            continue
        dedupe_key = (row["raw"].casefold(), row["canonical"].casefold(), row["slot"])
        if dedupe_key in seen_keys:
            rejections["duplicate_raw_canonical_slot"] += 1
            continue
        if row["raw"].casefold() in existing_raws:
            rejections["duplicate_existing_canonical_raw"] += 1
            continue
        seen_keys.add(dedupe_key)
        accepted.append(row)
        if len(accepted) >= MAX_ALIASES_PER_CANONICAL:
            break

    if len(accepted) < MIN_ALIASES_PER_CANONICAL and proposals:
        rejections["insufficient_aliases_after_filter"] += 1
    return accepted, rejections


def _normalize_row(
    proposal: Mapping[str, str],
    *,
    canonical: str,
    slot: str,
    pack_mode: str,
    real_import: bool = False,
) -> dict[str, str]:
    raw = (proposal.get("raw") or "").strip()
    source_note = (proposal.get("source_note") or proposal.get("note") or "").strip()
    note_prefix = "real_import_v0.1" if real_import else "dry_run_v0.1"
    note = f"{note_prefix};pack={pack_mode}"
    if source_note:
        note += f";source_note={source_note}"
    return {
        "raw": raw,
        "canonical": canonical,
        "slot": slot,
        "lang": "zh",
        "priority": "0",
        "rule_type": "alias",
        "review_status": "review",
        "ambiguity": _default_ambiguity(canonical),
        "tags": _default_tags(canonical, slot),
        "source": "ai_candidate",
        "note": note,
    }


def _reject_reason(
    row: dict[str, str],
    *,
    candidate_type: str,
    pack_mode: str,
    source_context: str = "",
) -> str | None:
    if not row["raw"]:
        return "missing_raw"
    if not row["canonical"]:
        return "missing_canonical"
    if _is_english_duplicate(row["raw"], row["canonical"]):
        return "raw_equals_canonical_english"
    if row["canonical"].casefold() == "gun" and pack_mode == "new_candidate":
        return "gun_not_allowed_new_candidate"
    if candidate_type == "phrase" and row["canonical"] in {"Single", "Shot"}:
        return "single_shot_phrase_split"
    for forbidden in FORBIDDEN_RAW_BY_CANONICAL.get(row["canonical"], ()):
        if forbidden in row["raw"]:
            return f"forbidden_raw_{forbidden}"
    if row["canonical"] == "Shot":
        lowered = f"{row['raw']} {source_context}".casefold()
        if _has_shot_microphone_context(lowered):
            return "forbidden_shot_microphone_context"
    if row["slot"] not in {
        "action",
        "material",
        "object",
        "source",
        "motion",
        "detail",
        "modifier",
        "unknown",
    }:
        return "invalid_slot"
    return None


def _is_english_duplicate(raw: str, canonical: str) -> bool:
    english = re.compile(r"[A-Za-z]+(?:[\s_-]+[A-Za-z]+)*")
    if not english.fullmatch(raw) or not english.fullmatch(canonical):
        return False
    normalize = lambda value: re.sub(r"[\s_-]+", " ", value.strip().casefold())
    return normalize(raw) == normalize(canonical)


def _has_shot_microphone_context(context: str) -> bool:
    if any(marker in context for marker in FORBIDDEN_SHOT_MARKERS):
        return True
    return re.search(r"\b(?:shotgun\s+)?mics?(?:rophones?)?\b", context) is not None


def _default_ambiguity(canonical: str) -> str:
    if canonical in {"Hit", "Crack", "Shot", "Gun", "Squeak", "Single Shot"}:
        return "high"
    if canonical in {"Impact", "Drop", "Ring", "Door"}:
        return "medium"
    return "low"


def _default_tags(canonical: str, slot: str) -> str:
    tags = {
        "Hit": "impact/hit",
        "Crack": "break/crack",
        "Shot": "weapon/shot",
        "Gun": "weapon/gun",
        "Squeak": "friction/squeak",
        "Single Shot": "weapon/phrase",
        "Impact": "impact",
        "Friction": "friction",
        "Chain": "object/chain",
        "Door": "object/door",
        "Drop": "drop",
        "Ring": "ring/tonal",
    }
    return tags.get(canonical, slot)


def _existing_raw_keys(path: Path) -> set[str]:
    return {token.raw.casefold() for token in load_canonical_rows(path)}


def _load_prompt_items(path: Path) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            items.append(json.loads(line))
    return items


def _require_reviewed_prompt_pack(path: Path, expected_directory: str) -> None:
    if path.parent.name != expected_directory:
        raise ValueError(
            f"Only the reviewed prompt pack is allowed: expected parent directory "
            f"{expected_directory}, got {path.parent.name}"
        )


def _read_import_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = {field.strip() for field in (reader.fieldnames or []) if field}
        missing = REQUIRED_IMPORT_COLUMNS - fieldnames
        if missing:
            raise ValueError(f"{path} is missing required import columns: {', '.join(sorted(missing))}")
        if "source_note" not in fieldnames and "note" not in fieldnames:
            raise ValueError(f"{path} is missing required import column: source_note")
        rows: list[dict[str, str]] = []
        for source_row in reader:
            row = {
                str(key).strip(): (value or "").strip()
                for key, value in source_row.items()
                if key is not None
            }
            row["source_note"] = row.get("source_note") or row.get("note", "")
            rows.append(row)
        return rows


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANONICAL_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_report(
    path: Path,
    *,
    summary: ImportSummary,
    pack_specs: tuple[tuple[str, Path], ...],
    import_csv: Path | None,
) -> None:
    lines = [
        "# AI Alias Candidates Review Report",
        "",
        (
            "Dry-run generation only. No AI runtime promotion and no canonical overwrite."
            if summary.dry_run
            else "Real AI output review import only. No AI runtime promotion and no canonical overwrite."
        ),
        "",
        f"- input_count: `{summary.input_count}`",
        f"- output_count: `{summary.candidate_count}`",
        f"- filtered_count: `{summary.rejected_count}`",
        f"- candidate_count: `{summary.candidate_count}`",
        f"- canonical_count: `{summary.canonical_count}`",
        f"- rejected_count: `{summary.rejected_count}`",
        f"- dry_run: `{str(summary.dry_run).lower()}`",
        f"- AI invoked: `no`",
        f"- promote: `no`",
        f"- keep appears: `{'yes' if summary.has_keep else 'no'}`",
        f"- has_keep: `{str(summary.has_keep).lower()}`",
        f"- all_source_ai_candidate: `{str(summary.all_source_ai_candidate).lower()}`",
        f"- all_priority_zero: `{str(summary.all_priority_zero).lower()}`",
        f"- gun_only_alias_expansion: `{str(summary.gun_only_alias_expansion).lower()}`",
        f"- canonical_tokens.csv changed: `{'yes' if summary.canonical_tokens_changed else 'no'}`",
        f"- CSV: `{summary.csv_path}`",
        "",
        "## Counts by canonical",
        "",
        *(f"- {canonical}: `{count}`" for canonical, count in summary.counts_by_canonical.items()),
        "",
        "## Counts by pack",
        "",
        *(f"- {pack}: `{count}`" for pack, count in summary.counts_by_pack.items()),
        "",
        "## Rejection reason counts",
        "",
        *(
            [f"- {reason}: `{count}`" for reason, count in summary.rejection_reason_counts.items()]
            or ["- none"]
        ),
        "",
        "## Inputs",
        "",
        *(f"- `{pack_path}` ({pack_mode})" for pack_mode, pack_path in pack_specs),
        *([f"- `{import_csv}`"] if import_csv else []),
        "",
        "## Canonical token guard",
        "",
        f"- canonical_tokens_sha256_before: `{summary.canonical_tokens_sha256_before}`",
        f"- canonical_tokens_sha256_after: `{summary.canonical_tokens_sha256_after}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _pack_from_note(note: str) -> str:
    match = re.search(r"pack=([a-z_]+)", note or "")
    return match.group(1) if match else ""


def _gun_only_alias_expansion(rows: list[dict[str, str]]) -> bool:
    gun_rows = [row for row in rows if row["canonical"].casefold() == "gun"]
    if not gun_rows:
        return True
    return all(_pack_from_note(row.get("note", "")) == "alias_expansion" for row in gun_rows)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--new-candidate-pack",
        type=Path,
        default=DEFAULT_NEW_CANDIDATE_PACK,
    )
    parser.add_argument(
        "--alias-expansion-pack",
        type=Path,
        default=DEFAULT_ALIAS_EXPANSION_PACK,
    )
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL_PATH)
    parser.add_argument(
        "--import-csv",
        type=Path,
        default=None,
        help="Optional pre-generated AI alias CSV to import and validate.",
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use deterministic mock aliases when --import-csv is not provided.",
    )
    args = parser.parse_args(argv)
    try:
        summary = import_ai_alias_candidates(
            args.new_candidate_pack,
            args.alias_expansion_pack,
            args.output_csv,
            args.report,
            args.canonical,
            import_csv=args.import_csv,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(
        f"input={summary.input_count} candidates={summary.candidate_count} "
        f"canonicals={summary.canonical_count} rejected={summary.rejected_count} "
        f"dry_run={str(summary.dry_run).lower()} "
        f"ai_invoked=no promote=no keep={str(summary.has_keep).lower()} "
        f"canonical_changed={str(summary.canonical_tokens_changed).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
