#!/usr/bin/env python3
"""BOOM One Mining v0.1 b001 safe-phase report and candidates.

This script reads aligned BOOM One Chinese/English FXName spreadsheets by Excel
row number, runs only the Chinese FXName through the governed normalizer, and
emits review artifacts. It never writes canonical_tokens.csv.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import zip_longest
from pathlib import Path
from typing import Iterable, Sequence

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fxengine.canonical_db import (  # noqa: E402
    DEFAULT_CANONICAL_PATH,
    FORBIDDEN_BROAD_ZH_TOKENS,
    load_canonical_rows,
    title_fx_text,
)
from fxengine.models import FXNameResult  # noqa: E402
from fxengine.normalizer import FXNameNormalizer  # noqa: E402
from glossary.fx_slots import infer_slot  # noqa: E402


BATCH = "boom_one_mining_v0.1_b001"
BATCH_ID = "boom_one_mining_v0_1_b001"
SOURCE = "boom_mined"
NOTE = BATCH

ZH_XLSX = ROOT / "docs" / "训练数据" / "BOOM ONE 中文音效目录.xlsx"
EN_XLSX = ROOT / "docs" / "训练数据" / "BOOM ONE 英文音效目录.xlsx"
OUTPUT_DIR = ROOT / "docs" / "boom_mining"
BEFORE_MD = OUTPUT_DIR / f"{BATCH_ID}_before.md"
CANDIDATES_CSV = OUTPUT_DIR / f"{BATCH_ID}_candidates.csv"
METRICS_JSON = OUTPUT_DIR / f"{BATCH_ID}_metrics.json"
SAMPLES_CSV = OUTPUT_DIR / f"{BATCH_ID}_samples.csv"
AFTER_METRICS_JSON = OUTPUT_DIR / f"{BATCH_ID}_after_metrics.json"
AFTER_SAMPLES_CSV = OUTPUT_DIR / f"{BATCH_ID}_after_samples.csv"

FXNAME_COLUMN = 10
DEFAULT_LIMIT = 1000

CANDIDATE_COLUMNS = (
    "batch",
    "row_number",
    "zh_fxname",
    "en_fxname",
    "unknown_raw",
    "suggested_raw",
    "suggested_canonical",
    "slot",
    "lang",
    "priority",
    "rule_type",
    "review_status",
    "ambiguity",
    "tags",
    "source",
    "note",
    "evidence",
    "skip_reason",
    "safety_notes",
    "candidate_status",
    "promote_ready",
)
SAMPLE_COLUMNS = (
    "row_number",
    "zh_fxname",
    "output_fxname",
    "en_fxname",
    "quality",
    "issues",
    "unknowns",
)

HEADER_MARKERS = {"fxname", "fx name", "fx_name", "外汇名称", "fx名称", "音效名称"}
TARGET_METADATA_TOKENS = {
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "i",
    "j",
    "k",
    "l",
    "m",
    "n",
    "o",
    "p",
    "q",
    "r",
    "s",
    "t",
    "u",
    "v",
    "w",
    "x",
    "y",
    "z",
    "take",
    "tk",
    "version",
    "ver",
    "alt",
    "alternate",
}
TEXT_TOKEN_RE = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)?|\d+(?:\.\d+)?")
ASCII_RE = re.compile(r"^[A-Za-z][A-Za-z -]*$")
ZH_RE = re.compile(r"[\u4e00-\u9fff]")
ACTION_CANONICALS = {
    "approach",
    "crack",
    "creak",
    "eat",
    "explosion",
    "fly",
    "fly away",
    "flyby",
    "friction",
    "grunt",
    "hit",
    "hum",
    "impact",
    "land",
    "rattle",
    "rev up",
    "ring",
    "roar",
    "roll",
    "scrape",
    "scratch",
    "scream",
    "shatter",
    "slide",
    "start",
    "switch off",
    "switch off sequence",
    "take off",
    "whoosh",
}
MATERIAL_CANONICALS = {
    "ceramic",
    "cloth",
    "fire",
    "glass",
    "leather",
    "metal",
    "paper",
    "plastic",
    "rubber",
    "stone",
    "water",
    "wood",
}
MODIFIER_CANONICALS = {"fast", "heavy", "light", "long", "short", "slow", "steady"}
DETAIL_CANONICALS = {"away", "close", "distant", "exterior", "interior", "sequence"}
OBJECT_CANONICALS = {
    "aircraft",
    "augusta",
    "bell",
    "bird",
    "boeing",
    "cabinet",
    "cat",
    "cow",
    "dog",
    "door",
    "drawer",
    "heli",
    "herd",
    "horse",
    "pigs",
    "pigs herd",
    "turbine",
    "wardrobe",
}

# Conservative deterministic evidence map. A row is emitted only when the
# Chinese surface appears in the dirty input and the English target contains the
# proposed canonical token/phrase in order.
ZH_TARGET_MAP: tuple[tuple[str, str], ...] = (
    ("重型", "Heavy"),
    ("沉重", "Heavy"),
    ("轻型", "Light"),
    ("木制", "Wood"),
    ("木头", "Wood"),
    ("木质", "Wood"),
    ("衣柜", "Wardrobe"),
    ("橱柜", "Cabinet"),
    ("柜子", "Cabinet"),
    ("抽屉", "Drawer"),
    ("门", "Door"),
    ("滑动", "Slide"),
    ("滑行", "Slide"),
    ("慢", "Slow"),
    ("快速", "Fast"),
    ("快", "Fast"),
    ("短", "Short"),
    ("长", "Long"),
    ("吱吱声", "Creak"),
    ("嘎吱", "Creak"),
    ("吱呀", "Creak"),
    ("咕噜声", "Grunt"),
    ("咆哮", "Roar"),
    ("吼叫", "Roar"),
    ("尖叫", "Scream"),
    ("吃", "Eat"),
    ("猪群", "Pigs Herd"),
    ("猪", "Pigs"),
    ("牛", "Cow"),
    ("马", "Horse"),
    ("狗", "Dog"),
    ("猫", "Cat"),
    ("鸟", "Bird"),
    ("群", "Herd"),
    ("内部", "Interior"),
    ("外部", "Exterior"),
    ("飞走", "Fly Away"),
    ("飞离", "Fly Away"),
    ("飞越", "Flyby"),
    ("飞过", "Flyby"),
    ("飞", "Fly"),
    ("飞行", "Fly"),
    ("直升机", "Heli"),
    ("飞机", "Aircraft"),
    ("奥古斯塔", "Augusta"),
    ("波音", "Boeing"),
    ("涡轮增压", "Turbine Rev Up"),
    ("涡轮", "Turbine"),
    ("启动", "Start"),
    ("起飞", "Take Off"),
    ("降落", "Land"),
    ("着陆", "Land"),
    ("关闭", "Switch Off"),
    ("开关关闭", "Switch Off"),
    ("开关关闭序列", "Switch Off Sequence"),
    ("稳定", "Steady"),
    ("序列", "Sequence"),
    ("接近", "Approach"),
    ("远离", "Away"),
    ("远处", "Distant"),
    ("近处", "Close"),
    ("近距", "Close"),
    ("金属", "Metal"),
    ("塑料", "Plastic"),
    ("玻璃", "Glass"),
    ("石头", "Stone"),
    ("布料", "Cloth"),
    ("橡胶", "Rubber"),
    ("陶瓷", "Ceramic"),
    ("皮革", "Leather"),
    ("纸", "Paper"),
    ("水", "Water"),
    ("火", "Fire"),
    ("撞击", "Impact"),
    ("冲击", "Impact"),
    ("碰撞", "Impact"),
    ("拍击", "Hit"),
    ("敲击", "Hit"),
    ("敲打", "Hit"),
    ("刮擦", "Scrape"),
    ("抓挠", "Scratch"),
    ("摩擦", "Friction"),
    ("滚动", "Roll"),
    ("摇晃", "Rattle"),
    ("嘎嘎声", "Rattle"),
    ("铃声", "Bell"),
    ("响铃", "Ring"),
    ("开裂", "Crack"),
    ("破裂", "Crack"),
    ("破碎", "Shatter"),
    ("爆炸", "Explosion"),
    ("呼啸", "Whoosh"),
    ("嗡嗡声", "Hum"),
    ("嗡嗡", "Hum"),
)


@dataclass(frozen=True)
class Pair:
    row_number: int
    zh_fxname: str
    en_fxname: str


@dataclass(frozen=True)
class AlignmentInfo:
    zh_sheet_title: str
    en_sheet_title: str
    zh_header_rows_skipped: int
    en_header_rows_skipped: int
    empty_pair_skipped: int
    first_row: int | None
    last_row: int | None
    pair_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "zh": {
                "sheet_title": self.zh_sheet_title,
                "header_rows_skipped": self.zh_header_rows_skipped,
                "first_row": self.first_row,
                "last_row": self.last_row,
            },
            "en": {
                "sheet_title": self.en_sheet_title,
                "header_rows_skipped": self.en_header_rows_skipped,
                "first_row": self.first_row,
                "last_row": self.last_row,
            },
            "empty_pair_skipped": self.empty_pair_skipped,
            "pair_count": self.pair_count,
        }


@dataclass
class CandidateRow:
    batch: str
    row_number: int
    zh_fxname: str
    en_fxname: str
    unknown_raw: str
    suggested_raw: str
    suggested_canonical: str
    slot: str
    lang: str
    priority: int
    rule_type: str
    review_status: str
    ambiguity: str
    tags: str
    source: str
    note: str
    evidence: str
    skip_reason: str
    safety_notes: str
    candidate_status: str
    promote_ready: bool
    evidence_key: str = field(default="", repr=False)

    def key(self) -> tuple[str, str]:
        return (self.lang, self.suggested_raw.casefold())

    def as_csv_row(self) -> dict[str, object]:
        out = {column: getattr(self, column) for column in CANDIDATE_COLUMNS}
        out["promote_ready"] = "true" if self.promote_ready else "false"
        return out


@dataclass(frozen=True)
class CaseAnalysis:
    pair: Pair
    output_fxname: str
    quality: str
    issues: tuple[str, ...]
    unknowns: tuple[str, ...]
    target_tokens: tuple[str, ...]
    output_tokens: tuple[str, ...]
    primary_status: str
    safety_issues: tuple[str, ...]
    existing_canonical_conflict: bool = False
    in_batch_conflict: bool = False


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _clean_cell(value: object) -> str:
    return "" if value is None else str(value).strip()


def _is_header(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value.strip()).casefold()
    compact = normalized.replace(" ", "").replace("_", "")
    return normalized in HEADER_MARKERS or compact in {"fxname", "fx名称", "外汇名称"}


def _iter_j_values(path: Path) -> tuple[str, Iterable[str]]:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    worksheet = workbook.active

    def values() -> Iterable[str]:
        try:
            for row in worksheet.iter_rows(values_only=True):
                value = row[FXNAME_COLUMN - 1] if len(row) >= FXNAME_COLUMN else None
                yield _clean_cell(value)
        finally:
            workbook.close()

    return worksheet.title, values()


def load_pairs(zh_path: Path, en_path: Path, limit: int) -> tuple[list[Pair], AlignmentInfo]:
    zh_title, zh_values = _iter_j_values(zh_path)
    en_title, en_values = _iter_j_values(en_path)
    zh_headers = 0
    en_headers = 0
    empty_pairs = 0
    pairs: list[Pair] = []

    for row_number, (zh_value, en_value) in enumerate(
        zip_longest(zh_values, en_values, fillvalue=""), start=1
    ):
        zh_is_header = _is_header(zh_value)
        en_is_header = _is_header(en_value)
        if zh_is_header or en_is_header:
            zh_headers += int(zh_is_header)
            en_headers += int(en_is_header)
            continue
        if not zh_value or not en_value:
            empty_pairs += 1
            continue
        pairs.append(Pair(row_number=row_number, zh_fxname=zh_value, en_fxname=en_value))
        if len(pairs) >= limit:
            break

    first_row = pairs[0].row_number if pairs else None
    last_row = pairs[-1].row_number if pairs else None
    return pairs, AlignmentInfo(
        zh_sheet_title=zh_title,
        en_sheet_title=en_title,
        zh_header_rows_skipped=zh_headers,
        en_header_rows_skipped=en_headers,
        empty_pair_skipped=empty_pairs,
        first_row=first_row,
        last_row=last_row,
        pair_count=len(pairs),
    )


def _target_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in TEXT_TOKEN_RE.findall(text):
        value = raw.casefold()
        if value.isdigit():
            continue
        if value in TARGET_METADATA_TOKENS:
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?k", value):
            continue
        tokens.append(value)
    return tokens


def _display_token(value: str) -> str:
    return title_fx_text(value.replace("-", " "))


def _is_subsequence(needle: Sequence[str], haystack: Sequence[str]) -> bool:
    if not needle:
        return False
    pos = 0
    for token in haystack:
        if token == needle[pos]:
            pos += 1
            if pos == len(needle):
                return True
    return False


def _ordered_match(output_tokens: Sequence[str], target_tokens: Sequence[str]) -> bool:
    if not output_tokens or not target_tokens:
        return False
    if list(output_tokens) == list(target_tokens):
        return True
    if _is_subsequence(output_tokens, target_tokens):
        return len(output_tokens) / len(target_tokens) >= 0.8
    if _is_subsequence(target_tokens, output_tokens):
        return len(target_tokens) / len(output_tokens) >= 0.8
    return False


def _token_phrase_in_target(canonical: str, target_tokens: Sequence[str]) -> bool:
    wanted = _target_tokens(canonical)
    if not wanted:
        return False
    return _is_subsequence(wanted, target_tokens)


def _has_zh(text: str) -> bool:
    return bool(ZH_RE.search(text))


def _has_ascii(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text))


def _lang_for_raw(raw: str) -> str:
    if _has_zh(raw) and _has_ascii(raw):
        return "mixed"
    if _has_zh(raw):
        return "zh"
    return "en"


def _skip_reason_for_raw(raw: str, target_supported: bool) -> str:
    if raw in FORBIDDEN_BROAD_ZH_TOKENS:
        return "forbidden_broad_token"
    if _has_zh(raw) and len(raw) == 1:
        return "single_char_zh"
    if re.fullmatch(r"\d+(?:\.\d+)?", raw.strip()):
        return "number_or_take_metadata"
    if re.fullmatch(r"[A-Z]{1,8}\d[A-Za-z0-9]*", raw.strip()):
        return "technical_metadata_only"
    if not target_supported:
        return "target_not_supporting"
    return "dirty_input_too_unstable"


def _existing_indexes() -> tuple[dict[tuple[str, str], set[str]], set[tuple[str, str, str]]]:
    raw_to_canonicals: dict[tuple[str, str], set[str]] = defaultdict(set)
    exact: set[tuple[str, str, str]] = set()
    for token in load_canonical_rows(DEFAULT_CANONICAL_PATH):
        key = (token.lang, token.raw.casefold())
        canonical_key = token.canonical.casefold()
        raw_to_canonicals[key].add(canonical_key)
        exact.add((token.lang, token.raw.casefold(), canonical_key))
    return raw_to_canonicals, exact


def _base_candidate(
    pair: Pair,
    *,
    unknown_raw: str,
    suggested_raw: str,
    suggested_canonical: str,
    evidence: str,
    skip_reason: str = "",
    safety_notes: str = "",
    candidate_status: str = "promote_ready",
    promote_ready: bool = True,
) -> CandidateRow:
    lang = _lang_for_raw(suggested_raw)
    return CandidateRow(
        batch=BATCH,
        row_number=pair.row_number,
        zh_fxname=pair.zh_fxname,
        en_fxname=pair.en_fxname,
        unknown_raw=unknown_raw,
        suggested_raw=suggested_raw,
        suggested_canonical=title_fx_text(suggested_canonical),
        slot=_slot_for_canonical(suggested_canonical),
        lang=lang,
        priority=0,
        rule_type="phrase",
        review_status="review",
        ambiguity="low",
        tags="boom_one_mining",
        source=SOURCE,
        note=NOTE,
        evidence=evidence,
        skip_reason=skip_reason,
        safety_notes=safety_notes,
        candidate_status=candidate_status,
        promote_ready=promote_ready,
        evidence_key=f"{pair.row_number}:{pair.en_fxname}",
    )


def _slot_for_canonical(canonical: str) -> str:
    normalized = " ".join(_target_tokens(canonical))
    if normalized in ACTION_CANONICALS:
        return "action"
    if normalized in MATERIAL_CANONICALS:
        return "material"
    if normalized in MODIFIER_CANONICALS:
        return "modifier"
    if normalized in DETAIL_CANONICALS:
        return "detail"
    if normalized in OBJECT_CANONICALS:
        return "object"
    inferred = infer_slot(canonical)
    return inferred if inferred != "unknown" else "unknown"


def _safe_candidate(raw: str, canonical: str, target_tokens: Sequence[str]) -> tuple[bool, str]:
    if not _token_phrase_in_target(canonical, target_tokens):
        return False, "candidate_without_target_evidence"
    if raw in FORBIDDEN_BROAD_ZH_TOKENS:
        return False, "forbidden_broad_token"
    if _has_zh(raw) and len(raw) == 1:
        return False, "single_char_zh"
    if not raw.strip() or not canonical.strip():
        return False, "missing_raw_or_canonical"
    return True, ""


def _match_unknown(raw: str, unknowns: Sequence[str]) -> str:
    for unknown in unknowns:
        if raw == unknown or raw in unknown or unknown in raw:
            return unknown
    return raw


def generate_candidates(pair: Pair, result: FXNameResult) -> list[CandidateRow]:
    target_tokens = _target_tokens(pair.en_fxname)
    target_token_set = set(target_tokens)
    rows: list[CandidateRow] = []
    emitted: set[tuple[str, str, str]] = set()

    for raw in result.unknowns:
        if ASCII_RE.fullmatch(raw.strip()):
            raw_tokens = _target_tokens(raw)
            if raw_tokens and _is_subsequence(raw_tokens, target_tokens):
                canonical = " ".join(_display_token(token) for token in raw_tokens)
                ok, safety = _safe_candidate(raw, canonical, target_tokens)
                rows.append(
                    _base_candidate(
                        pair,
                        unknown_raw=raw,
                        suggested_raw=raw,
                        suggested_canonical=canonical,
                        evidence=f"english_exact_target_match:{canonical}",
                        skip_reason="" if ok else safety,
                        safety_notes=safety,
                        candidate_status="promote_ready" if ok else "unsafe",
                        promote_ready=ok,
                    )
                )
                emitted.add((_lang_for_raw(raw), raw.casefold(), canonical.casefold()))

    for raw, canonical in ZH_TARGET_MAP:
        if raw not in pair.zh_fxname:
            continue
        if not _token_phrase_in_target(canonical, target_tokens):
            continue
        unknown_raw = _match_unknown(raw, result.unknowns)
        key = (_lang_for_raw(raw), raw.casefold(), canonical.casefold())
        if key in emitted:
            continue
        ok, safety = _safe_candidate(raw, canonical, target_tokens)
        rows.append(
            _base_candidate(
                pair,
                unknown_raw=unknown_raw,
                suggested_raw=raw,
                suggested_canonical=canonical,
                evidence=f"zh_surface_in_input;target_contains:{canonical}",
                skip_reason="" if ok else safety,
                safety_notes=safety,
                candidate_status="promote_ready" if ok else "unsafe",
                promote_ready=ok,
            )
        )
        emitted.add(key)

    for raw in result.unknowns:
        if any(row.unknown_raw == raw for row in rows):
            continue
        target_supported = raw.casefold() in target_token_set
        rows.append(
            _base_candidate(
                pair,
                unknown_raw=raw,
                suggested_raw="",
                suggested_canonical="",
                evidence="",
                skip_reason=_skip_reason_for_raw(raw, target_supported),
                candidate_status="skipped",
                promote_ready=False,
            )
        )
    return rows


def _apply_existing_conflicts(candidates: list[CandidateRow]) -> None:
    existing_by_raw, existing_exact = _existing_indexes()
    for row in candidates:
        if not row.suggested_raw or not row.suggested_canonical:
            continue
        key = row.key()
        canonical = row.suggested_canonical.casefold()
        if (row.lang, row.suggested_raw.casefold(), canonical) in existing_exact:
            row.candidate_status = "skipped"
            row.promote_ready = False
            row.skip_reason = "already_covered"
            continue
        existing = existing_by_raw.get(key, set())
        if existing and canonical not in existing:
            row.candidate_status = "conflict"
            row.promote_ready = False
            row.skip_reason = "existing_canonical_conflict"
            row.safety_notes = _append_note(row.safety_notes, "existing_canonical_conflict")


def _apply_in_batch_conflicts(candidates: list[CandidateRow]) -> None:
    canonicals_by_key: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in candidates:
        if row.suggested_raw and row.suggested_canonical and row.candidate_status != "skipped":
            canonicals_by_key[row.key()].add(row.suggested_canonical.casefold())
    conflict_keys = {key for key, values in canonicals_by_key.items() if len(values) > 1}
    for row in candidates:
        if row.key() in conflict_keys:
            row.candidate_status = "conflict"
            row.promote_ready = False
            row.skip_reason = "in_batch_conflict"
            row.safety_notes = _append_note(row.safety_notes, "in_batch_conflict")


def _append_note(existing: str, note: str) -> str:
    parts = [part for part in existing.split(";") if part]
    if note not in parts:
        parts.append(note)
    return ";".join(parts)


def _safety_issues(result: FXNameResult, candidates: Sequence[CandidateRow]) -> list[str]:
    issues: list[str] = []
    if result.debug.get("nllb_fallback_used") is True:
        issues.append("nllb_fallback_used")
    for token in result.tokens:
        if token.contributes_to_fxname and any(issue.startswith("unknown_") for issue in token.issues):
            issues.append(f"unknown_contributes_to_fxname:{token.raw}")
        if token.contributes_to_fxname and (
            token.source == "canonical_review" or "canonical_review_required" in token.issues
        ):
            issues.append(f"review_token_runtime_output:{token.raw}")
    if result.boom_suggestion and result.output_fxname == result.boom_suggestion:
        issues.append("boom_suggestion_replaced_final_output")
    for row in candidates:
        if row.promote_ready and row.suggested_raw in FORBIDDEN_BROAD_ZH_TOKENS:
            issues.append(f"forbidden_broad_proposed:{row.suggested_raw}")
        if row.promote_ready and _has_zh(row.suggested_raw) and len(row.suggested_raw) == 1:
            issues.append(f"single_char_zh_proposed:{row.suggested_raw}")
        if row.promote_ready and not row.evidence:
            issues.append(f"candidate_without_target_evidence:{row.suggested_raw}")
    return sorted(set(issues))


def _primary_status(result: FXNameResult, output_tokens: Sequence[str], target_tokens: Sequence[str]) -> str:
    if _ordered_match(output_tokens, target_tokens) and not result.unknowns:
        return "pass"
    if result.unknowns and not result.output_fxname:
        return "unknown"
    if result.quality == "needs_review" or any("canonical_review_required" in issue for issue in result.issues):
        return "needs_review"
    if result.output_fxname:
        return "partial"
    return "unknown"


def analyze(pairs: Sequence[Pair]) -> tuple[list[CaseAnalysis], list[CandidateRow]]:
    normalizer = FXNameNormalizer()
    analyses: list[CaseAnalysis] = []
    candidates: list[CandidateRow] = []

    for pair in pairs:
        result = normalizer.normalize(pair.zh_fxname)
        output_tokens = tuple(_target_tokens(result.output_fxname))
        target_tokens = tuple(_target_tokens(pair.en_fxname))
        row_candidates = generate_candidates(pair, result)
        candidates.extend(row_candidates)
        safety = _safety_issues(result, row_candidates)
        analyses.append(
            CaseAnalysis(
                pair=pair,
                output_fxname=result.output_fxname,
                quality=result.quality,
                issues=tuple(result.issues),
                unknowns=tuple(result.unknowns),
                target_tokens=target_tokens,
                output_tokens=output_tokens,
                primary_status=_primary_status(result, output_tokens, target_tokens),
                safety_issues=tuple(safety),
            )
        )

    _apply_existing_conflicts(candidates)
    _apply_in_batch_conflicts(candidates)
    conflict_rows = {
        row.row_number: row.skip_reason
        for row in candidates
        if row.skip_reason in {"existing_canonical_conflict", "in_batch_conflict"}
    }
    updated: list[CaseAnalysis] = []
    for analysis in analyses:
        reason = conflict_rows.get(analysis.pair.row_number, "")
        updated.append(
            CaseAnalysis(
                pair=analysis.pair,
                output_fxname=analysis.output_fxname,
                quality=analysis.quality,
                issues=analysis.issues,
                unknowns=analysis.unknowns,
                target_tokens=analysis.target_tokens,
                output_tokens=analysis.output_tokens,
                primary_status=analysis.primary_status,
                safety_issues=analysis.safety_issues,
                existing_canonical_conflict=reason == "existing_canonical_conflict",
                in_batch_conflict=reason == "in_batch_conflict",
            )
        )
    return updated, candidates


def _metrics(
    analyses: Sequence[CaseAnalysis],
    candidates: Sequence[CandidateRow],
    alignment: AlignmentInfo,
    canonical_before: str,
    canonical_after: str,
    limit: int,
) -> dict[str, object]:
    unknowns = Counter(raw for analysis in analyses for raw in analysis.unknowns)
    skip_reasons = Counter(row.skip_reason for row in candidates if row.skip_reason)
    slot_distribution = Counter(row.slot for row in candidates if row.promote_ready)
    existing_conflicts = sum(
        1 for row in candidates if row.skip_reason == "existing_canonical_conflict"
    )
    in_batch_conflicts = sum(1 for row in candidates if row.skip_reason == "in_batch_conflict")
    forbidden_ready = sorted(
        {row.suggested_raw for row in candidates if row.promote_ready and row.suggested_raw in FORBIDDEN_BROAD_ZH_TOKENS}
    )
    single_char_ready = sorted(
        {
            row.suggested_raw
            for row in candidates
            if row.promote_ready and _has_zh(row.suggested_raw) and len(row.suggested_raw) == 1
        }
    )
    before = {
        "total": len(analyses),
        "pass": sum(analysis.primary_status == "pass" for analysis in analyses),
        "partial": sum(analysis.primary_status == "partial" for analysis in analyses),
        "needs_review": sum(analysis.primary_status == "needs_review" for analysis in analyses),
        "unknown": sum(bool(analysis.unknowns) for analysis in analyses),
        "safety_fail": sum(bool(analysis.safety_issues) for analysis in analyses),
        "conflict": sum(
            analysis.existing_canonical_conflict or analysis.in_batch_conflict
            for analysis in analyses
        ),
    }
    return {
        "batch": BATCH,
        "range": {
            "first_row": alignment.first_row,
            "last_row": alignment.last_row,
            "limit": limit,
        },
        "pair_count": len(analyses),
        "alignment": alignment.to_dict(),
        "before": before,
        "top_unknowns": [
            {"unknown": raw, "count": count} for raw, count in unknowns.most_common(20)
        ],
        "candidate_count": len(candidates),
        "promote_ready_candidate_count": sum(row.promote_ready for row in candidates),
        "skip_reason_counts": dict(sorted(skip_reasons.items())),
        "slot_distribution": dict(sorted(slot_distribution.items())),
        "safety_fail_count": before["safety_fail"],
        "conflict_count": existing_conflicts + in_batch_conflicts,
        "existing_canonical_conflict_count": existing_conflicts,
        "in_batch_conflict_count": in_batch_conflicts,
        "forbidden_broad_check": {
            "passed": not forbidden_ready,
            "tokens": forbidden_ready,
        },
        "single_char_keep_check": {
            "passed": not single_char_ready,
            "tokens": single_char_ready,
        },
        "canonical_sha256_before": canonical_before,
        "canonical_sha256_after": canonical_after,
        "canonical_changed": canonical_before != canonical_after,
        "source": SOURCE,
        "note": NOTE,
        "ai_invoked": False,
        "promote": False,
    }


def _candidate_ranking(candidates: Sequence[CandidateRow]) -> list[tuple[tuple[str, str], int, int, CandidateRow]]:
    grouped: dict[tuple[str, str], list[CandidateRow]] = defaultdict(list)
    for row in candidates:
        if row.promote_ready:
            grouped[(row.suggested_raw, row.suggested_canonical)].append(row)
    ranked: list[tuple[tuple[str, str], int, int, CandidateRow]] = []
    for key, rows in grouped.items():
        evidence_diversity = len({row.evidence_key for row in rows})
        ranked.append((key, len(rows), evidence_diversity, rows[0]))
    ranked.sort(key=lambda item: (-item[1], -item[2], item[0][0], item[0][1]))
    return ranked


def _md(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def write_candidates(path: Path, candidates: Sequence[CandidateRow]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANDIDATE_COLUMNS)
        writer.writeheader()
        for row in candidates:
            writer.writerow(row.as_csv_row())


def write_samples(path: Path, analyses: Sequence[CaseAnalysis]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SAMPLE_COLUMNS)
        writer.writeheader()
        for analysis in analyses:
            writer.writerow(
                {
                    "row_number": analysis.pair.row_number,
                    "zh_fxname": analysis.pair.zh_fxname,
                    "output_fxname": analysis.output_fxname,
                    "en_fxname": analysis.pair.en_fxname,
                    "quality": analysis.quality,
                    "issues": ";".join(analysis.issues),
                    "unknowns": ";".join(analysis.unknowns),
                }
            )


def write_report(
    path: Path,
    analyses: Sequence[CaseAnalysis],
    candidates: Sequence[CandidateRow],
    metrics: dict[str, object],
    alignment: AlignmentInfo,
) -> None:
    before = metrics["before"]
    assert isinstance(before, dict)
    top_unknowns = metrics["top_unknowns"]
    assert isinstance(top_unknowns, list)
    ranked_candidates = _candidate_ranking(candidates)
    partials = [analysis for analysis in analyses if analysis.primary_status == "partial"][:20]
    needs_review = [
        analysis for analysis in analyses if analysis.primary_status == "needs_review"
    ][:20]
    safety = [analysis for analysis in analyses if analysis.safety_issues]
    conflicts = [
        row
        for row in candidates
        if row.skip_reason in {"existing_canonical_conflict", "in_batch_conflict"}
    ]
    skipped = Counter(row.skip_reason for row in candidates if row.skip_reason).most_common(20)

    lines = [
        "# BOOM One Mining v0.1 b001 Before Report",
        "",
        "## Batch",
        "",
        f"- batch: `{BATCH}`",
        f"- source: `{SOURCE}`",
        f"- note: `{NOTE}`",
        "- phase: `safe_before_only`",
        "- canonical write: `no`",
        "- AI invoked: `no`",
        "- promote: `no`",
        "",
        "## Data Range",
        "",
        f"- zh sheet title: `{alignment.zh_sheet_title}`",
        f"- en sheet title: `{alignment.en_sheet_title}`",
        f"- zh header_rows_skipped: `{alignment.zh_header_rows_skipped}`",
        f"- en header_rows_skipped: `{alignment.en_header_rows_skipped}`",
        f"- empty_pair_skipped: `{alignment.empty_pair_skipped}`",
        f"- valid pair count: `{alignment.pair_count}`",
        f"- valid Excel row range: `{alignment.first_row}` - `{alignment.last_row}`",
        "- alignment rule: same Excel row number only; no compressed zip.",
        "",
        "## Before Metrics",
        "",
        "| metric | count |",
        "| --- | ---: |",
    ]
    for key in ("pass", "partial", "needs_review", "unknown", "safety_fail", "conflict"):
        lines.append(f"| {key} | {before.get(key, 0)} |")
    lines.extend(
        [
            "",
            "## Top 20 Unknown",
            "",
            "| unknown | count |",
            "| --- | ---: |",
        ]
    )
    for item in top_unknowns[:20]:
        assert isinstance(item, dict)
        lines.append(f"| {_md(item['unknown'])} | {item['count']} |")

    lines.extend(
        [
            "",
            "## Top 20 Candidate",
            "",
            "Only `promote_ready=true` candidates are shown here. Skipped, unsafe, and conflict rows are kept out of this primary list.",
            "",
            "| suggested_raw | suggested_canonical | slot | freq | evidence_diversity |",
            "| --- | --- | --- | ---: | ---: |",
        ]
    )
    for (_key, freq, diversity, row) in ranked_candidates[:20]:
        lines.append(
            f"| {_md(row.suggested_raw)} | {_md(row.suggested_canonical)} | {row.slot} | {freq} | {diversity} |"
        )

    lines.extend(["", "## Top 20 Partial Samples", ""])
    lines.append("| row | zh_fxname | output_fxname | en_fxname |")
    lines.append("| ---: | --- | --- | --- |")
    for analysis in partials:
        lines.append(
            f"| {analysis.pair.row_number} | {_md(analysis.pair.zh_fxname)} | {_md(analysis.output_fxname)} | {_md(analysis.pair.en_fxname)} |"
        )

    lines.extend(["", "## Top 20 Needs Review Samples", ""])
    lines.append("| row | zh_fxname | output_fxname | en_fxname | issues | unknowns |")
    lines.append("| ---: | --- | --- | --- | --- | --- |")
    for analysis in needs_review:
        lines.append(
            f"| {analysis.pair.row_number} | {_md(analysis.pair.zh_fxname)} | {_md(analysis.output_fxname)} | {_md(analysis.pair.en_fxname)} | {_md(';'.join(analysis.issues))} | {_md(';'.join(analysis.unknowns))} |"
        )

    lines.extend(["", "## Safety Fail Details", ""])
    if not safety:
        lines.append("- none")
    else:
        lines.append("| row | zh_fxname | issues |")
        lines.append("| ---: | --- | --- |")
        for analysis in safety[:50]:
            lines.append(
                f"| {analysis.pair.row_number} | {_md(analysis.pair.zh_fxname)} | {_md(';'.join(analysis.safety_issues))} |"
            )

    lines.extend(["", "## Conflict Details", ""])
    if not conflicts:
        lines.append("- none")
    else:
        lines.append("| row | type | raw | canonical | evidence |")
        lines.append("| ---: | --- | --- | --- | --- |")
        for row in conflicts[:50]:
            lines.append(
                f"| {row.row_number} | {row.skip_reason} | {_md(row.suggested_raw)} | {_md(row.suggested_canonical)} | {_md(row.evidence)} |"
            )

    lines.extend(
        [
            "",
            "## Top 20 Skip Reasons",
            "",
            "| skip_reason | count |",
            "| --- | ---: |",
        ]
    )
    for reason, count in skipped:
        lines.append(f"| {reason} | {count} |")

    forbidden_check = metrics["forbidden_broad_check"]
    single_check = metrics["single_char_keep_check"]
    assert isinstance(forbidden_check, dict)
    assert isinstance(single_check, dict)
    lines.extend(
        [
            "",
            "## Forbidden Broad Check",
            "",
            f"- passed: `{str(forbidden_check['passed']).lower()}`",
            f"- tokens: `{', '.join(forbidden_check['tokens']) if forbidden_check['tokens'] else ''}`",
            "",
            "## Single Char Keep Check",
            "",
            f"- passed: `{str(single_check['passed']).lower()}`",
            f"- tokens: `{', '.join(single_check['tokens']) if single_check['tokens'] else ''}`",
            "",
            "## Canonical Write Policy",
            "",
            "- This is a safe phase. The script does not write `fxengine/data/canonical_tokens.csv`.",
            "- All candidates remain `review_status=review` and `priority=0`.",
            "- `promote_ready=true` only means a later human/script promote phase may consider the row.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_metrics(path: Path, metrics: dict[str, object]) -> None:
    path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    canonical_before = _sha256(DEFAULT_CANONICAL_PATH)
    pairs, alignment = load_pairs(args.zh_xlsx, args.en_xlsx, args.limit)
    analyses, candidates = analyze(pairs)
    canonical_after = _sha256(DEFAULT_CANONICAL_PATH)
    if canonical_before != canonical_after:
        raise RuntimeError("canonical_tokens.csv changed during safe phase")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics = _metrics(analyses, candidates, alignment, canonical_before, canonical_after, args.limit)
    if args.after:
        # After mode never rewrites the before-state artifacts (before.md,
        # candidates.csv, before metrics); it only records current-state metrics.
        write_metrics(args.after_metrics_json, metrics)
        if args.dump_samples:
            write_samples(args.after_samples_csv, analyses)
    else:
        write_candidates(args.candidates_csv, candidates)
        write_report(args.before_md, analyses, candidates, metrics, alignment)
        write_metrics(args.metrics_json, metrics)
        if args.dump_samples:
            write_samples(args.samples_csv, analyses)

    before = metrics["before"]
    assert isinstance(before, dict)
    print(
        " ".join(
            [
                f"batch={BATCH}",
                f"mode={'after' if args.after else 'before'}",
                f"pairs={len(pairs)}",
                f"rows={alignment.first_row}-{alignment.last_row}",
                f"pass={before['pass']}",
                f"partial={before['partial']}",
                f"needs_review={before['needs_review']}",
                f"unknown={before['unknown']}",
                f"safety_fail={before['safety_fail']}",
                f"conflict={before['conflict']}",
                f"candidates={len(candidates)}",
                f"promote_ready={metrics['promote_ready_candidate_count']}",
                f"canonical_changed={'true' if metrics['canonical_changed'] else 'false'}",
                "ai_invoked=no",
                f"promote={'recorded' if args.after else 'no'}",
            ]
        )
    )
    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zh-xlsx", type=Path, default=ZH_XLSX)
    parser.add_argument("--en-xlsx", type=Path, default=EN_XLSX)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--before-md", type=Path, default=BEFORE_MD)
    parser.add_argument("--candidates-csv", type=Path, default=CANDIDATES_CSV)
    parser.add_argument("--metrics-json", type=Path, default=METRICS_JSON)
    parser.add_argument("--samples-csv", type=Path, default=SAMPLES_CSV)
    parser.add_argument("--dump-samples", action="store_true")
    parser.add_argument(
        "--after",
        action="store_true",
        help="After mode: record current-state metrics without touching before artifacts.",
    )
    parser.add_argument("--after-metrics-json", type=Path, default=AFTER_METRICS_JSON)
    parser.add_argument("--after-samples-csv", type=Path, default=AFTER_SAMPLES_CSV)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
