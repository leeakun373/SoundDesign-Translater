#!/usr/bin/env python3
"""Build a review-only workbench from real Chinese FXName inputs.

This tool runs the deterministic normalizer, compares governed expectations when
available, and writes candidate/review artifacts.  It never edits the canonical
table, promotes rows, or invokes an external AI service.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fxengine.canonical_db import (  # noqa: E402
    DEFAULT_CANONICAL_PATH,
    CanonicalDB,
    CanonicalToken,
    load_canonical_rows,
)
from fxengine.normalizer import FXNameNormalizer  # noqa: E402


DEFAULT_PRIMARY_CASES = (
    ROOT / "tests" / "zh_fxname_governance_cases_150.csv",
    ROOT / "tests" / "zh_fxname_governance_cases_50.csv",
)
DEFAULT_DISCOVERY_ROOTS = tuple(ROOT / name for name in ("tests", "docs", "exports", "data"))
DEFAULT_CANDIDATE_PATHS = (
    ROOT / "exports" / "ai_alias_prompt_pack" / "ai_alias_candidates_surface_cleaned.csv",
    ROOT / "exports" / "ai_alias_prompt_pack" / "ai_alias_candidates_decision_recommendations_v2.csv",
    ROOT / "exports" / "ai_alias_prompt_pack" / "promote_plan_batch0_v2.csv",
)
DEFAULT_OUTPUT_CSV = ROOT / "exports" / "alias_workbench" / "zh_alias_review_workbench.csv"
DEFAULT_BATCH_REPORT = ROOT / "reports" / "zh_alias_batch_test_report.md"
DEFAULT_GAP_REPORT = ROOT / "reports" / "zh_alias_gap_analysis_report.md"

WORKBENCH_COLUMNS = (
    "case_id",
    "input_text",
    "current_fxname",
    "current_status",
    "unknown_tokens",
    "review_tokens",
    "suggested_raw",
    "suggested_canonical",
    "suggested_slot",
    "suggestion_type",
    "decision",
    "decision_reason",
    "source",
    "priority",
    "next_action",
)
CURRENT_STATUSES = ("pass", "partial", "unknown", "conflict", "needs_review")
GAP_TYPES = (
    "missing_alias",
    "missing_phrase",
    "slot_mismatch",
    "surface_suffix",
    "duplicate_raw_conflict",
    "canonical_exists_but_raw_missing",
    "rule_bug",
    "no_action",
)
INPUT_COLUMNS = ("input_text", "input", "中文输入")
SURFACE_SUFFIXES = ("声音", "音效", "声效", "声", "音")
SURFACE_EXCEPTIONS = frozenset(
    {
        "枪声",
        "脚步声",
        "风声",
        "开门声",
        "关门声",
        "门轴吱响",
        "回响声",
        "回声",
        "尾音",
        "余响",
    }
)
SAFE_ALIAS_SEEDS: dict[str, tuple[str, str]] = {
    "摩擦": ("Friction", "action"),
    "擦蹭": ("Friction", "action"),
    "刮擦": ("Scrape", "action"),
    "铁链": ("Chain", "object"),
    "锁链": ("Chain", "object"),
}
MARKDOWN_CASE_HEADINGS = ("示例清单", "脏输入")
SKIP_DISCOVERY_PARTS = frozenset({"results", "alias_workbench", "训练数据"})


@dataclass(frozen=True)
class InputCase:
    case_id: str
    input_text: str
    source_path: str
    expected_canonical: str = ""
    expected_fxname: str = ""
    expected_source: str = ""
    confidence_band: str = ""
    must_not_contain: str = ""


@dataclass(frozen=True)
class CandidateInfo:
    lookup_raw: str
    effective_raw: str
    canonical: str
    slot: str
    decision: str
    conflict_group: str
    surface_action: str
    source_path: str


@dataclass
class WorkbenchEntry:
    row: dict[str, str]
    gap_type: str
    confidence: str = "human"


@dataclass
class CaseAnalysis:
    case: InputCase
    status: str
    current_fxname: str
    unknown_tokens: list[str]
    review_tokens: list[str]
    expected_mismatch: bool
    entries: list[WorkbenchEntry] = field(default_factory=list)
    missing_canonicals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WorkbenchSummary:
    case_count: int
    workbench_row_count: int
    status_counts: dict[str, int]
    unknown_top: list[tuple[str, int]]
    suggested_alias_top: list[tuple[str, str, int]]
    direct_alias_candidate_count: int
    high_confidence_candidate_count: int
    human_candidate_count: int
    existing_ai_candidate_count: int
    scanned_file_count: int
    source_case_counts: dict[str, int]
    output_csv: str
    batch_report: str
    gap_report: str
    canonical_tokens_sha256_before: str
    canonical_tokens_sha256_after: str
    canonical_tokens_changed: bool
    promote: bool = False
    ai_invoked: bool = False


class CanonicalIndex:
    def __init__(self, rows: Sequence[CanonicalToken]) -> None:
        self.rows = list(rows)
        self.raws = {row.raw for row in rows}
        self.review_raws = {row.raw for row in rows if row.review_status == "review"}
        self.canonical_slots: dict[str, Counter[str]] = defaultdict(Counter)
        raw_canonicals: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            if row.canonical:
                self.canonical_slots[_norm(row.canonical)][_workbench_slot(row.slot)] += 1
                raw_canonicals[row.raw].add(_norm(row.canonical))
        self.conflict_raws = {raw for raw, values in raw_canonicals.items() if len(values) > 1}

    def canonical_exists(self, canonical: str) -> bool:
        return _norm(canonical) in self.canonical_slots

    def slot_for(self, canonical: str) -> str:
        counts = self.canonical_slots.get(_norm(canonical))
        if not counts:
            return "phrase" if " " in canonical.strip() else "detail"
        return counts.most_common(1)[0][0]

    def canonical_is_unambiguous(self, canonical: str) -> bool:
        counts = self.canonical_slots.get(_norm(canonical))
        return bool(counts) and len(counts) == 1


class CandidateIndex:
    def __init__(self, candidates: Sequence[CandidateInfo]) -> None:
        by_raw: dict[str, list[CandidateInfo]] = defaultdict(list)
        for item in candidates:
            for raw in {item.lookup_raw, item.effective_raw}:
                if raw:
                    by_raw[raw].append(item)
        self.by_raw = dict(by_raw)
        self.conflict_raws = {
            raw
            for raw, items in self.by_raw.items()
            if len({_norm(item.canonical) for item in items if item.canonical}) > 1
            or any(item.conflict_group for item in items)
        }

    def get(self, raw: str) -> CandidateInfo | None:
        items = self.by_raw.get(raw, [])
        if not items:
            return None
        rank = {"accept_candidate": 0, "needs_review": 1, "reject_candidate": 2, "": 3}
        return sorted(items, key=lambda item: (rank.get(item.decision, 3), item.canonical, item.slot))[0]

    def canonicals(self, raw: str) -> list[str]:
        return sorted({item.canonical for item in self.by_raw.get(raw, []) if item.canonical})


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).casefold()


def _contains_zh(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _split_alternatives(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split("|") if part.strip()]


def _first_alternative(value: str) -> str:
    alternatives = _split_alternatives(value)
    return alternatives[0] if alternatives else ""


def _workbench_slot(slot: str) -> str:
    slot = (slot or "").strip().lower()
    if slot in {"action", "object", "material", "detail", "phrase"}:
        return slot
    if slot in {"motion"}:
        return "action"
    if slot in {"source"}:
        return "object"
    return "detail"


def load_case_csv(path: Path | str) -> list[InputCase]:
    """Read one structured case CSV with an input/input_text column."""
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        input_column = next((name for name in INPUT_COLUMNS if name in fieldnames), None)
        if input_column is None:
            return []
        cases: list[InputCase] = []
        for row_number, row in enumerate(reader, start=1):
            input_text = (row.get(input_column) or "").strip()
            if not input_text or not _contains_zh(input_text):
                continue
            raw_id = (row.get("case_id") or row.get("id") or str(row_number)).strip()
            cases.append(
                InputCase(
                    case_id=raw_id,
                    input_text=input_text,
                    source_path=_relative(path),
                    expected_canonical=(row.get("expected_canonical") or "").strip(),
                    expected_fxname=(row.get("expected_fxname") or "").strip(),
                    expected_source=(row.get("expected_source") or "").strip(),
                    confidence_band=(row.get("confidence_band") or "").strip().lower(),
                    must_not_contain=(row.get("must_not_contain") or "").strip(),
                )
            )
        return cases


def _markdown_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_markdown_separator(cells: Sequence[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def _clean_markdown_input(text: str) -> str:
    text = re.sub(r"[`*_]", "", text).strip()
    return text.strip("「」『』\"' ")


def _expand_markdown_input(text: str) -> list[str]:
    cleaned = _clean_markdown_input(text)
    if not cleaned:
        return []
    if " / " in cleaned and len(cleaned) <= 30:
        return [_clean_markdown_input(part) for part in cleaned.split(" / ") if _contains_zh(part)]
    return [cleaned]


def load_markdown_cases(path: Path | str) -> list[InputCase]:
    """Extract explicit Chinese-input tables and named example lists from Markdown/text."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    cases: list[InputCase] = []
    serial = 0
    index = 0
    active_case_heading = False
    while index < len(lines):
        line = lines[index]
        if line.lstrip().startswith("#"):
            active_case_heading = any(marker in line for marker in MARKDOWN_CASE_HEADINGS)
        if line.strip().startswith("|") and index + 1 < len(lines):
            headers = _markdown_cells(line)
            separator = _markdown_cells(lines[index + 1])
            input_index = next(
                (position for position, header in enumerate(headers) if header in {"中文输入", "input", "input_text"}),
                None,
            )
            if input_index is not None and _is_markdown_separator(separator):
                expected_index = next(
                    (position for position, header in enumerate(headers) if header == "expected_fxname"),
                    None,
                )
                index += 2
                while index < len(lines) and lines[index].strip().startswith("|"):
                    cells = _markdown_cells(lines[index])
                    if input_index < len(cells):
                        for input_text in _expand_markdown_input(cells[input_index]):
                            if _contains_zh(input_text) and len(input_text) <= 100:
                                serial += 1
                                expected = cells[expected_index].strip() if expected_index is not None and expected_index < len(cells) else ""
                                cases.append(
                                    InputCase(
                                        case_id=f"{path.stem}:md{serial:03d}",
                                        input_text=input_text,
                                        source_path=_relative(path),
                                        expected_fxname=expected,
                                    )
                                )
                    index += 1
                continue
        if active_case_heading and line.strip() and not line.lstrip().startswith(("#", "|", ">", "```")):
            pieces = [part.strip() for part in line.split("·")] if "·" in line else []
            if len(pieces) > 1:
                for piece in pieces:
                    input_text = _clean_markdown_input(piece)
                    if _contains_zh(input_text) and len(input_text) <= 100:
                        serial += 1
                        cases.append(
                            InputCase(
                                case_id=f"{path.stem}:md{serial:03d}",
                                input_text=input_text,
                                source_path=_relative(path),
                            )
                        )
        index += 1
    return cases


def discover_input_cases(
    primary_paths: Sequence[Path] = DEFAULT_PRIMARY_CASES,
    discovery_roots: Sequence[Path] = DEFAULT_DISCOVERY_ROOTS,
    *,
    discover_extra: bool = True,
) -> tuple[list[InputCase], int, dict[str, int]]:
    """Load primary batches, then add unique structured cases found in scoped roots."""
    cases: list[InputCase] = []
    primary_keys: set[tuple[str, str]] = set()
    primary_inputs: set[str] = set()
    scanned_files: set[Path] = set()

    for path in primary_paths:
        path = Path(path)
        if not path.is_file():
            continue
        scanned_files.add(path.resolve())
        for item in load_case_csv(path):
            key = (item.case_id, item.input_text)
            if key in primary_keys:
                continue
            primary_keys.add(key)
            primary_inputs.add(item.input_text)
            cases.append(item)

    if discover_extra:
        seen_extra_inputs = set(primary_inputs)
        primary_resolved = {Path(path).resolve() for path in primary_paths}
        files: list[Path] = []
        for root in discovery_roots:
            root = Path(root)
            if not root.is_dir():
                continue
            for pattern in ("*.csv", "*.md", "*.txt"):
                files.extend(root.rglob(pattern))
        for path in sorted(set(files), key=lambda item: item.as_posix().casefold()):
            if path.resolve() in primary_resolved or any(part in SKIP_DISCOVERY_PARTS for part in path.parts):
                continue
            scanned_files.add(path.resolve())
            try:
                found = load_case_csv(path) if path.suffix.lower() == ".csv" else load_markdown_cases(path)
            except (csv.Error, UnicodeError, OSError):
                continue
            for item in found:
                if item.input_text in seen_extra_inputs:
                    continue
                seen_extra_inputs.add(item.input_text)
                cases.append(
                    replace(item, case_id=f"{path.stem}:{item.case_id}")
                    if path.suffix.lower() == ".csv"
                    else item
                )

    source_counts = Counter(item.source_path for item in cases)
    return cases, len(scanned_files), dict(sorted(source_counts.items()))


def load_ai_candidate_index(paths: Sequence[Path] = DEFAULT_CANDIDATE_PATHS) -> CandidateIndex:
    candidates: list[CandidateInfo] = []
    seen: set[tuple[str, str, str, str, str, str]] = set()
    for path in paths:
        path = Path(path)
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                original_raw = (row.get("original_raw") or row.get("raw") or "").strip()
                raw = (row.get("raw") or original_raw).strip()
                cleaned_raw = (row.get("cleaned_raw") or "").strip()
                surface_action = (row.get("surface_action") or "").strip()
                effective_raw = cleaned_raw if surface_action in {"replace_raw", "needs_review"} and cleaned_raw else raw
                canonical = (row.get("canonical") or "").strip()
                slot = _workbench_slot(row.get("slot") or "")
                decision = (row.get("decision_recommendation") or "").strip()
                conflict_group = (row.get("conflict_group") or "").strip()
                if not original_raw or not canonical:
                    continue
                key = (
                    original_raw,
                    effective_raw,
                    canonical,
                    slot,
                    conflict_group,
                    decision,
                )
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    CandidateInfo(
                        lookup_raw=original_raw,
                        effective_raw=effective_raw,
                        canonical=canonical,
                        slot=slot,
                        decision=decision,
                        conflict_group=conflict_group,
                        surface_action=surface_action,
                        source_path=_relative(path),
                    )
                )
                if raw and raw != original_raw:
                    candidates.append(
                        CandidateInfo(
                            lookup_raw=raw,
                            effective_raw=effective_raw,
                            canonical=canonical,
                            slot=slot,
                            decision=decision,
                            conflict_group=conflict_group,
                            surface_action=surface_action,
                            source_path=_relative(path),
                        )
                    )
    return CandidateIndex(candidates)


def _expected_fxname_matches(actual: str, expected: str) -> bool:
    alternatives = _split_alternatives(expected)
    if not alternatives:
        return True
    actual_words = _norm(actual).split()
    for alternative in alternatives:
        expected_words = _norm(alternative).split()
        if actual_words == expected_words:
            return True
        width = len(expected_words)
        if width and any(actual_words[start : start + width] == expected_words for start in range(len(actual_words) - width + 1)):
            return True
    return False


def _expected_mismatch(case: InputCase, current_fxname: str) -> bool:
    if case.expected_fxname and not _expected_fxname_matches(current_fxname, case.expected_fxname):
        return True
    current_norm = _norm(current_fxname)
    return any(_norm(value) in current_norm for value in _split_alternatives(case.must_not_contain))


def _missing_expected_words(expected_fxname: str, current_fxname: str) -> str:
    expected = _first_alternative(expected_fxname)
    if not expected:
        return ""
    remaining = Counter(_norm(current_fxname).split())
    missing: list[str] = []
    for word in expected.split():
        key = word.casefold()
        if remaining[key]:
            remaining[key] -= 1
        else:
            missing.append(word)
    return " ".join(missing)


def _case_missing_canonicals(case: InputCase, current_fxname: str) -> list[str]:
    if case.expected_canonical:
        current = _norm(current_fxname)
        missing = [value for value in _split_alternatives(case.expected_canonical) if _norm(value) not in current]
        if missing:
            return [missing[0]]
    derived = _missing_expected_words(case.expected_fxname, current_fxname)
    return [derived] if derived else []


def _clean_surface(raw: str) -> tuple[str, str]:
    if raw in SURFACE_SUFFIXES:
        return "", "standalone_surface_suffix_requires_review"
    if raw in SURFACE_EXCEPTIONS:
        return "", "surface_exception_requires_review"
    for suffix in SURFACE_SUFFIXES:
        if raw.endswith(suffix):
            stem = raw[: -len(suffix)].strip()
            if len(stem) >= 2 and _contains_zh(stem):
                return stem, f"strip_suffix_{suffix}"
    return raw, ""


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _base_row(
    analysis: CaseAnalysis,
    *,
    suggested_raw: str = "",
    suggested_canonical: str = "",
    suggested_slot: str = "",
    suggestion_type: str,
    decision_reason: str,
    source: str = "batch_test_candidate",
    next_action: str,
) -> dict[str, str]:
    reason = ";".join(
        part for part in (decision_reason, f"case_source={analysis.case.source_path}") if part
    )
    return {
        "case_id": analysis.case.case_id,
        "input_text": analysis.case.input_text,
        "current_fxname": analysis.current_fxname,
        "current_status": analysis.status,
        "unknown_tokens": ";".join(analysis.unknown_tokens),
        "review_tokens": ";".join(analysis.review_tokens),
        "suggested_raw": suggested_raw,
        "suggested_canonical": suggested_canonical,
        "suggested_slot": suggested_slot,
        "suggestion_type": suggestion_type,
        "decision": "pending",
        "decision_reason": reason,
        "source": source,
        "priority": "0",
        "next_action": next_action,
    }


def _candidate_entry(
    analysis: CaseAnalysis,
    raw: str,
    candidate: CandidateInfo,
    canonical_index: CanonicalIndex,
) -> WorkbenchEntry:
    effective_raw = candidate.effective_raw or raw
    surface_changed = effective_raw != raw
    suggestion_type = "surface_cleanup_needed" if surface_changed else "existing_alias_missing"
    confidence = "high" if candidate.decision == "accept_candidate" and not surface_changed else "human"
    reason = ";".join(
        part
        for part in (
            "existing_ai_candidate",
            f"candidate_decision={candidate.decision or 'pending'}",
            f"candidate_source={candidate.source_path}",
            "confidence=high" if confidence == "high" else "needs_human_decision",
        )
        if part
    )
    gap_type = "surface_suffix" if surface_changed else (
        "canonical_exists_but_raw_missing" if canonical_index.canonical_exists(candidate.canonical) else "missing_alias"
    )
    return WorkbenchEntry(
        _base_row(
            analysis,
            suggested_raw=effective_raw,
            suggested_canonical=candidate.canonical,
            suggested_slot=candidate.slot,
            suggestion_type=suggestion_type,
            decision_reason=reason,
            source="existing_ai_candidate",
            next_action="review_existing_candidate",
        ),
        gap_type,
        confidence,
    )


def _derive_status(
    *,
    unknown_tokens: Sequence[str],
    review_tokens: Sequence[str],
    has_mapped: bool,
    conflict: bool,
    expected_mismatch: bool,
    result_quality: str,
) -> str:
    if conflict:
        return "conflict"
    if review_tokens:
        return "needs_review"
    if unknown_tokens:
        return "partial" if has_mapped else "unknown"
    if expected_mismatch or result_quality != "pass":
        return "needs_review"
    return "pass"


def analyze_cases(
    cases: Sequence[InputCase],
    *,
    normalizer: FXNameNormalizer,
    canonical_index: CanonicalIndex,
    candidate_index: CandidateIndex,
) -> list[CaseAnalysis]:
    analyses: list[CaseAnalysis] = []
    for case in cases:
        result = normalizer.normalize(case.input_text)
        unresolved = _unique(
            token.raw
            for token in result.tokens
            if token.decision == "unknown" or token.source == "unknown_review"
        )
        review_tokens = _unique(
            token.raw for token in result.tokens if "canonical_review_required" in token.issues
        )
        unknown_tokens = [raw for raw in unresolved if raw not in set(review_tokens)]
        mapped_tokens = [
            token
            for token in result.tokens
            if token.text and token.status in {"ok", "needs_review"}
        ]
        mismatch = _expected_mismatch(case, result.output_fxname)
        conflict_raws = set(unresolved) | {case.input_text}
        conflict = bool(
            conflict_raws & (canonical_index.conflict_raws | candidate_index.conflict_raws)
        )
        status = _derive_status(
            unknown_tokens=unknown_tokens,
            review_tokens=review_tokens,
            has_mapped=bool(mapped_tokens),
            conflict=conflict,
            expected_mismatch=mismatch,
            result_quality=result.quality,
        )
        analysis = CaseAnalysis(
            case=case,
            status=status,
            current_fxname=result.output_fxname,
            unknown_tokens=unknown_tokens,
            review_tokens=review_tokens,
            expected_mismatch=mismatch,
            missing_canonicals=_case_missing_canonicals(case, result.output_fxname),
        )

        if conflict:
            raw = next((value for value in conflict_raws if value in candidate_index.conflict_raws), unresolved[0] if unresolved else case.input_text)
            candidate = candidate_index.get(raw)
            canonicals = candidate_index.canonicals(raw)
            analysis.entries.append(
                WorkbenchEntry(
                    _base_row(
                        analysis,
                        suggested_raw=(candidate.effective_raw if candidate else raw),
                        suggested_canonical="|".join(canonicals),
                        suggested_slot=(candidate.slot if candidate else "action"),
                        suggestion_type="needs_human_decision",
                        decision_reason="duplicate_raw_conflict;needs_human_decision",
                        source="existing_ai_candidate" if candidate else "batch_test_candidate",
                        next_action="needs_user_review",
                    ),
                    "duplicate_raw_conflict",
                )
            )

        exact_candidate = candidate_index.get(case.input_text)
        if (
            not conflict
            and exact_candidate is not None
            and case.input_text not in canonical_index.raws
            and (unresolved or mismatch)
        ):
            analysis.entries.append(
                _candidate_entry(analysis, case.input_text, exact_candidate, canonical_index)
            )

        unresolved_for_phrase = list(unresolved)
        make_phrase = bool(
            not conflict
            and exact_candidate is None
            and len(unresolved_for_phrase) > 1
            and case.expected_fxname
            and case.input_text not in canonical_index.raws
            and len(case.input_text) <= 24
        )
        if make_phrase:
            suggested_canonical = _first_alternative(case.expected_fxname)
            analysis.entries.append(
                WorkbenchEntry(
                    _base_row(
                        analysis,
                        suggested_raw=case.input_text,
                        suggested_canonical=suggested_canonical,
                        suggested_slot="phrase",
                        suggestion_type="phrase_missing",
                        decision_reason="multiple_unresolved_tokens;needs_human_decision",
                        next_action="add_phrase_candidate",
                    ),
                    "missing_phrase",
                )
            )

        for raw in unknown_tokens:
            if conflict or make_phrase or (exact_candidate is not None and case.input_text == raw):
                continue
            if raw in canonical_index.raws:
                analysis.entries.append(
                    WorkbenchEntry(
                        _base_row(
                            analysis,
                            suggestion_type="no_action",
                            decision_reason=f"existing_canonical_raw={raw};needs_human_decision",
                            next_action="needs_user_review",
                        ),
                        "no_action",
                    )
                )
                continue
            candidate = candidate_index.get(raw)
            if candidate is not None:
                analysis.entries.append(_candidate_entry(analysis, raw, candidate, canonical_index))
                continue

            full_expected = _first_alternative(case.expected_fxname)
            if (
                len(unknown_tokens) == 1
                and not review_tokens
                and raw == case.input_text
                and " " in full_expected
            ):
                analysis.entries.append(
                    WorkbenchEntry(
                        _base_row(
                            analysis,
                            suggested_raw=case.input_text,
                            suggested_canonical=full_expected,
                            suggested_slot="phrase",
                            suggestion_type="phrase_missing",
                            decision_reason="whole_input_unresolved;needs_human_decision",
                            next_action="add_phrase_candidate",
                        ),
                        "missing_phrase",
                    )
                )
                continue

            cleaned_raw, surface_reason = _clean_surface(raw)
            if surface_reason.endswith("requires_review"):
                analysis.entries.append(
                    WorkbenchEntry(
                        _base_row(
                            analysis,
                            suggestion_type="surface_cleanup_needed",
                            decision_reason=f"{surface_reason};raw={raw};needs_human_decision",
                            next_action="needs_user_review",
                        ),
                        "surface_suffix",
                    )
                )
                continue
            suggestion_raw = cleaned_raw or raw
            seed = SAFE_ALIAS_SEEDS.get(suggestion_raw)
            suggested_canonical = seed[0] if seed else ""
            suggested_slot = seed[1] if seed else ""
            missing = _missing_expected_words(case.expected_fxname, result.output_fxname)
            expected_canonical = _first_alternative(case.expected_canonical)
            expected_canonical_missing = bool(
                expected_canonical and _norm(expected_canonical) not in _norm(result.output_fxname)
            )
            if (
                not suggested_canonical
                and len(unknown_tokens) == 1
                and not review_tokens
                and len(suggestion_raw) >= 2
            ):
                if missing and len(missing.split()) == 1:
                    suggested_canonical = missing
                elif expected_canonical_missing and len(expected_canonical.split()) == 1:
                    suggested_canonical = expected_canonical
            if suggested_canonical and not suggested_slot:
                suggested_slot = canonical_index.slot_for(suggested_canonical)

            mapped_slots = {
                _workbench_slot(token.slot)
                for token in mapped_tokens
                if token.canonical and token.slot != "unknown"
            }
            if (
                suggested_canonical
                and seed is None
                and suggested_slot in {"action", "object", "material"}
                and suggested_slot in mapped_slots
            ):
                suggested_canonical = ""
                suggested_slot = ""

            surface_changed = suggestion_raw != raw
            direct = bool(seed and suggestion_raw not in canonical_index.raws and not surface_changed)
            if suggested_canonical:
                canonical_known = canonical_index.canonical_exists(suggested_canonical)
                canonical_unambiguous = canonical_index.canonical_is_unambiguous(suggested_canonical)
                if surface_changed:
                    suggestion_type = "surface_cleanup_needed"
                    next_action = "needs_user_review"
                elif canonical_known and canonical_unambiguous:
                    suggestion_type = "existing_alias_missing"
                    next_action = "add_alias_candidate"
                else:
                    suggestion_type = "needs_human_decision"
                    next_action = "needs_user_review"
                reason = ";".join(
                    part
                    for part in (
                        surface_reason,
                        "canonical_exists_but_raw_missing" if canonical_known else "missing_alias",
                        "canonical_slot_ambiguous" if canonical_known and not canonical_unambiguous else "",
                        "confidence=high" if direct else "needs_human_decision",
                    )
                    if part
                )
                gap_type = "surface_suffix" if surface_changed else (
                    "canonical_exists_but_raw_missing" if canonical_index.canonical_exists(suggested_canonical) else "missing_alias"
                )
            else:
                suggestion_type = "surface_cleanup_needed" if surface_changed else "needs_human_decision"
                next_action = "needs_user_review"
                reason = ";".join(
                    part
                    for part in (
                        surface_reason,
                        "canonical_mapping_uncertain",
                        "needs_human_decision",
                    )
                    if part
                )
                gap_type = "surface_suffix" if surface_changed else "missing_alias"
            analysis.entries.append(
                WorkbenchEntry(
                    _base_row(
                        analysis,
                        suggested_raw=suggestion_raw,
                        suggested_canonical=suggested_canonical,
                        suggested_slot=suggested_slot,
                        suggestion_type=suggestion_type,
                        decision_reason=reason,
                        next_action=next_action,
                    ),
                    gap_type,
                    "high" if direct else "human",
                )
            )

        for raw in review_tokens:
            if conflict or make_phrase:
                continue
            analysis.entries.append(
                WorkbenchEntry(
                    _base_row(
                        analysis,
                        suggestion_type="no_action",
                        decision_reason=f"canonical_review_row_exists={raw};do_not_duplicate_raw;needs_human_decision",
                        next_action="needs_user_review",
                    ),
                    "no_action",
                )
            )

        slot_mismatches = [
            token
            for token in mapped_tokens
            if mismatch and token.source == "glossary_fallback" and token.slot == "unknown"
        ]
        for token in slot_mismatches:
            analysis.entries.append(
                WorkbenchEntry(
                    _base_row(
                        analysis,
                        suggested_raw=token.raw,
                        suggested_canonical=token.canonical or token.text,
                        suggested_slot=canonical_index.slot_for(token.canonical or token.text),
                        suggestion_type="slot_mismatch",
                        decision_reason="glossary_fallback_unknown_slot;expected_output_mismatch",
                        next_action="adjust_rule",
                    ),
                    "slot_mismatch",
                )
            )

        if mismatch and not unresolved:
            analysis.entries.append(
                WorkbenchEntry(
                    _base_row(
                        analysis,
                        suggested_raw=case.input_text,
                        suggested_canonical=_first_alternative(case.expected_canonical) or _first_alternative(case.expected_fxname),
                        suggested_slot="phrase",
                        suggestion_type="needs_human_decision",
                        decision_reason="normalized_output_does_not_match_governed_expectation;rule_bug",
                        next_action="adjust_rule",
                    ),
                    "rule_bug",
                )
            )

        if not analysis.entries:
            analysis.entries.append(
                WorkbenchEntry(
                    _base_row(
                        analysis,
                        suggestion_type="no_action",
                        decision_reason="normalize_result_accepted" if status == "pass" else "needs_human_decision",
                        next_action="ignore" if status == "pass" else "needs_user_review",
                    ),
                    "no_action",
                )
            )
        analyses.append(analysis)
    return analyses


def write_workbench_csv(path: Path | str, analyses: Sequence[CaseAnalysis]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=WORKBENCH_COLUMNS)
        writer.writeheader()
        for analysis in analyses:
            for entry in analysis.entries:
                writer.writerow({column: entry.row.get(column, "") for column in WORKBENCH_COLUMNS})


def _all_entries(analyses: Sequence[CaseAnalysis]) -> list[WorkbenchEntry]:
    return [entry for analysis in analyses for entry in analysis.entries]


def _candidate_key(entry: WorkbenchEntry) -> tuple[str, str, str]:
    row = entry.row
    return (row["suggested_raw"], row["suggested_canonical"], row["suggested_slot"])


def _build_summary(
    analyses: Sequence[CaseAnalysis],
    *,
    output_csv: Path,
    batch_report: Path,
    gap_report: Path,
    scanned_file_count: int,
    source_case_counts: dict[str, int],
    canonical_before: str,
    canonical_after: str,
) -> WorkbenchSummary:
    entries = _all_entries(analyses)
    status_counter = Counter(analysis.status for analysis in analyses)
    unknown_counter = Counter(
        raw for analysis in analyses for raw in analysis.unknown_tokens + analysis.review_tokens
    )
    alias_counter: Counter[tuple[str, str]] = Counter()
    for entry in entries:
        row = entry.row
        if row["suggested_raw"] and row["suggested_canonical"] and row["next_action"] in {
            "add_alias_candidate",
            "review_existing_candidate",
        }:
            alias_counter[(row["suggested_raw"], row["suggested_canonical"])] += 1
    actionable = {
        _candidate_key(entry): entry
        for entry in entries
        if entry.row["suggested_raw"]
    }
    high = {key for key, entry in actionable.items() if entry.confidence == "high"}
    human = set(actionable) - high
    direct_aliases = {
        _candidate_key(entry)
        for entry in entries
        if entry.row["next_action"] == "add_alias_candidate"
        and entry.row["suggested_raw"]
        and entry.row["suggested_canonical"]
    }
    existing = {
        _candidate_key(entry)
        for entry in entries
        if entry.row["source"] == "existing_ai_candidate"
    }
    return WorkbenchSummary(
        case_count=len(analyses),
        workbench_row_count=len(entries),
        status_counts={status: status_counter[status] for status in CURRENT_STATUSES},
        unknown_top=unknown_counter.most_common(50),
        suggested_alias_top=[(raw, canonical, count) for (raw, canonical), count in alias_counter.most_common(50)],
        direct_alias_candidate_count=len(direct_aliases),
        high_confidence_candidate_count=len(high),
        human_candidate_count=len(human),
        existing_ai_candidate_count=len(existing),
        scanned_file_count=scanned_file_count,
        source_case_counts=source_case_counts,
        output_csv=str(output_csv),
        batch_report=str(batch_report),
        gap_report=str(gap_report),
        canonical_tokens_sha256_before=canonical_before,
        canonical_tokens_sha256_after=canonical_after,
        canonical_tokens_changed=canonical_before != canonical_after,
    )


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        cells = [str(value).replace("|", "\\|").replace("\n", " ") for value in row]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def write_batch_report(
    path: Path | str,
    analyses: Sequence[CaseAnalysis],
    summary: WorkbenchSummary,
) -> None:
    path = Path(path)
    entries = _all_entries(analyses)
    missing_counter = Counter(
        canonical for analysis in analyses for canonical in analysis.missing_canonicals if canonical
    )
    suggestion_counter: Counter[tuple[str, str, str, str]] = Counter()
    for entry in entries:
        row = entry.row
        if (
            row["suggested_raw"]
            and row["suggested_canonical"]
            and row["next_action"] in {"add_alias_candidate", "review_existing_candidate"}
        ):
            suggestion_counter[(row["suggested_raw"], row["suggested_canonical"], row["suggested_slot"], row["next_action"])] += 1
    high_entries: dict[tuple[str, str, str], WorkbenchEntry] = {}
    for entry in entries:
        if entry.confidence == "high":
            high_entries[_candidate_key(entry)] = entry

    lines = [
        "# Chinese Alias Batch Test Report",
        "",
        "## Summary",
        "",
        f"- test case total: **{summary.case_count}**",
        f"- workbench row total: **{summary.workbench_row_count}**",
        f"- pass: **{summary.status_counts['pass']}**",
        f"- partial: **{summary.status_counts['partial']}**",
        f"- unknown: **{summary.status_counts['unknown']}**",
        f"- conflict: **{summary.status_counts['conflict']}**",
        f"- needs_review: **{summary.status_counts['needs_review']}**",
        f"- directly addable alias candidates (review rows only): **{summary.direct_alias_candidate_count}**",
        f"- directly actionable high-confidence candidates: **{summary.high_confidence_candidate_count}**",
        f"- candidates requiring human decision: **{summary.human_candidate_count}**",
        f"- existing AI candidates matched by real-input gaps and not active in canonical runtime: **{summary.existing_ai_candidate_count}**",
        f"- scanned structured files: **{summary.scanned_file_count}**",
        "",
        "## Unknown token top 50",
        "",
    ]
    lines.extend(_markdown_table(("rank", "token", "count"), [(index, raw, count) for index, (raw, count) in enumerate(summary.unknown_top, start=1)]))
    lines.extend(["", "## Most common missing canonical top 30", ""])
    lines.extend(_markdown_table(("rank", "canonical", "count"), [(index, raw, count) for index, (raw, count) in enumerate(missing_counter.most_common(30), start=1)]))
    lines.extend(["", "## Suggested alias candidates", ""])
    lines.extend(
        _markdown_table(
            ("raw", "canonical", "slot", "occurrences", "next_action"),
            [(raw, canonical, slot, count, action) for (raw, canonical, slot, action), count in suggestion_counter.most_common(50)],
        )
    )
    lines.extend(["", "## Recommended next batch", ""])
    if high_entries:
        lines.extend(
            _markdown_table(
                ("raw", "canonical", "slot", "source", "next_action"),
                [
                    (
                        entry.row["suggested_raw"],
                        entry.row["suggested_canonical"],
                        entry.row["suggested_slot"],
                        entry.row["source"],
                        entry.row["next_action"],
                    )
                    for _, entry in sorted(high_entries.items())
                ],
            )
        )
    else:
        lines.append("No high-confidence candidate met the review-only threshold.")
    lines.extend(["", "## Case sources", ""])
    lines.extend(_markdown_table(("source", "case_count"), list(summary.source_case_counts.items())))
    lines.extend(
        [
            "",
            "## Safety",
            "",
            f"- canonical_tokens_sha256_before: `{summary.canonical_tokens_sha256_before}`",
            f"- canonical_tokens_sha256_after: `{summary.canonical_tokens_sha256_after}`",
            f"- canonical changed: **{'yes' if summary.canonical_tokens_changed else 'no'}**",
            "- AI invoked: **no**",
            "- promote: **no**",
            "- all decisions remain: **pending**",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_gap_report(path: Path | str, analyses: Sequence[CaseAnalysis], summary: WorkbenchSummary) -> None:
    path = Path(path)
    grouped: dict[str, list[WorkbenchEntry]] = {gap_type: [] for gap_type in GAP_TYPES}
    for entry in _all_entries(analyses):
        grouped[entry.gap_type].append(entry)
    lines = [
        "# Chinese Alias Gap Analysis Report",
        "",
        "This report groups review-only workbench rows. No row is promoted or written to runtime.",
        "",
    ]
    for gap_type in GAP_TYPES:
        entries = grouped[gap_type]
        lines.extend([f"## {gap_type}", "", f"Count: **{len(entries)}**", ""])
        rows = [
            (
                entry.row["case_id"],
                entry.row["input_text"],
                entry.row["current_fxname"],
                entry.row["suggested_raw"],
                entry.row["suggested_canonical"],
                entry.row["next_action"],
            )
            for entry in entries[:50]
        ]
        if rows:
            lines.extend(_markdown_table(("case_id", "input", "current", "suggested_raw", "canonical", "next_action"), rows))
        else:
            lines.append("No cases.")
        lines.append("")
    lines.extend(
        [
            "## Safety",
            "",
            f"- canonical changed: **{'yes' if summary.canonical_tokens_changed else 'no'}**",
            "- AI invoked: **no**",
            "- promote: **no**",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_zh_alias_workbench(
    *,
    primary_paths: Sequence[Path] = DEFAULT_PRIMARY_CASES,
    discovery_roots: Sequence[Path] = DEFAULT_DISCOVERY_ROOTS,
    discover_extra: bool = True,
    candidate_paths: Sequence[Path] = DEFAULT_CANDIDATE_PATHS,
    canonical_path: Path = DEFAULT_CANONICAL_PATH,
    output_csv: Path = DEFAULT_OUTPUT_CSV,
    batch_report: Path = DEFAULT_BATCH_REPORT,
    gap_report: Path = DEFAULT_GAP_REPORT,
) -> WorkbenchSummary:
    canonical_path = Path(canonical_path)
    if not canonical_path.is_file():
        raise FileNotFoundError(f"Required canonical table not found: {canonical_path}")
    canonical_before = _sha256(canonical_path)
    canonical_rows = load_canonical_rows(canonical_path)
    canonical_index = CanonicalIndex(canonical_rows)
    candidate_index = load_ai_candidate_index(candidate_paths)
    cases, scanned_file_count, source_case_counts = discover_input_cases(
        primary_paths,
        discovery_roots,
        discover_extra=discover_extra,
    )
    if not cases:
        raise ValueError("No Chinese input cases found")
    normalizer = FXNameNormalizer(canonical_db=CanonicalDB(canonical_path=canonical_path))
    analyses = analyze_cases(
        cases,
        normalizer=normalizer,
        canonical_index=canonical_index,
        candidate_index=candidate_index,
    )
    output_csv = Path(output_csv)
    batch_report = Path(batch_report)
    gap_report = Path(gap_report)
    write_workbench_csv(output_csv, analyses)
    canonical_after = _sha256(canonical_path)
    if canonical_after != canonical_before:
        raise RuntimeError("canonical_tokens.csv changed while building alias workbench")
    summary = _build_summary(
        analyses,
        output_csv=output_csv,
        batch_report=batch_report,
        gap_report=gap_report,
        scanned_file_count=scanned_file_count,
        source_case_counts=source_case_counts,
        canonical_before=canonical_before,
        canonical_after=canonical_after,
    )
    write_batch_report(batch_report, analyses, summary)
    write_gap_report(gap_report, analyses, summary)
    final_hash = _sha256(canonical_path)
    if final_hash != canonical_before:
        raise RuntimeError("canonical_tokens.csv changed while writing alias workbench reports")
    return summary


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _print_summary(summary: WorkbenchSummary) -> None:
    counts = summary.status_counts
    print(
        "zh alias workbench: "
        f"cases={summary.case_count} rows={summary.workbench_row_count} "
        f"pass={counts['pass']} partial={counts['partial']} unknown={counts['unknown']} "
        f"conflict={counts['conflict']} needs_review={counts['needs_review']}"
    )
    print(
        f"high_confidence={summary.high_confidence_candidate_count} "
        f"direct_alias={summary.direct_alias_candidate_count} "
        f"human={summary.human_candidate_count} existing_ai={summary.existing_ai_candidate_count}"
    )
    print(f"workbench={summary.output_csv}")
    print(f"batch_report={summary.batch_report}")
    print(f"gap_report={summary.gap_report}")
    print("canonical changed=no; promote=no; AI invoked=no")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a review-only Chinese alias workbench")
    parser.add_argument("--case-csv", action="append", type=Path, dest="case_csvs")
    parser.add_argument("--no-discovery", action="store_true")
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL_PATH)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--batch-report", type=Path, default=DEFAULT_BATCH_REPORT)
    parser.add_argument("--gap-report", type=Path, default=DEFAULT_GAP_REPORT)
    args = parser.parse_args(argv)
    summary = build_zh_alias_workbench(
        primary_paths=tuple(args.case_csvs) if args.case_csvs else DEFAULT_PRIMARY_CASES,
        discover_extra=not args.no_discovery,
        canonical_path=args.canonical,
        output_csv=args.output_csv,
        batch_report=args.batch_report,
        gap_report=args.gap_report,
    )
    _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
