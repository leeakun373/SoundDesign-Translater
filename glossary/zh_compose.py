"""中文描述 → 英文 FX 名/关键词：术语表最长匹配组装，不依赖 NLLB 碎句。"""

from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from glossary.zh_normalize import normalize_fxname_input
from glossary.fx_slots import SlotTerm, infer_slot, split_slot_terms
from glossary.matcher import GlossaryEntry, GlossaryMatcher

ORAL_CSV = Path(__file__).resolve().parent / "zh_oral_aliases.csv"
FX_PATTERN_CSV = Path(__file__).resolve().parent / "packs" / "zh_fx_patterns.csv"

# 跳过虚词/量词/口语连接（不参与输出）
FILLER_CHARS = frozenset("的了下着在与和及或就还把被让给跟从向以很更最里来去到")
FILLER_PHRASES = (
    "一下",
    "几声",
    "一点",
    "有点",
    "然后",
    "里面",
    "那种",
    "感觉",
    "声音",
    "音效",
    "效果",
    "的声",
    "一声",
    "正在",
    "非常",
    "比较",
    "特别",
)

PUNCT = re.compile(r"[\s，。、；：！？,.!?;:\(\)（）\[\]【】\"'""]+")
ASCII_WORD = re.compile(r"[A-Za-z][A-Za-z0-9+\-]*")
ZH_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")

MIN_FX_PATTERN_FALLBACK: tuple[tuple[str, str, str, int], ...] = (
    ("木门", "Wood Door", "object", 100),
    ("木头", "Wood", "material", 100),
    ("木制", "Wood", "material", 100),
    ("门", "Door", "object", 90),
    ("滑开", "Slide Open", "action", 100),
    ("滑动", "Slide", "action", 100),
)


@dataclass(frozen=True)
class ComposeDiagnostics:
    text: str
    glossary_hits: int
    coverage: float
    unknown_zh: list[str] = field(default_factory=list)
    matched_terms: list[dict[str, str | int]] = field(default_factory=list)
    slots: list[SlotTerm] = field(default_factory=list)


def _split_zh_variants(zh: str) -> list[str]:
    parts: list[str] = []
    for chunk in re.split(r"[、，/,]", zh):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts or [zh.strip()]


def _load_oral_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {
        "外面": "Exterior",
        "户外": "Outdoor",
        "开过去": "Driveby",
        "开过去呼呼的": "Driveby Whoosh",
        "呼呼的": "Whoosh",
        "呼呼": "Whoosh",
        "带混响": "Reverberant",
        "混响": "Reverberant",
        "弓": "Bow",
        "弓搭箭": "Bow Nocked",
        "搭箭": "Nocked",
        "拧螺丝": "Screw",
        "咔哒几声": "Clicks",
        "咔哒": "Clicks",
        "关上": "Shut",
        "关闭": "Closing",
        "空办公室": "Empty Office",
        "办公室": "Office",
        "空": "Empty",
        "摩擦声": "Friction",
        "刮擦声": "Scratch",
        "汽车": "Car",
        "房间": "Room",
        "室外": "Exterior",
        "停止": "Stop",
        "撕裂": "Tear",
        "打碎": "Shatter",
    }
    if ORAL_CSV.is_file():
        with ORAL_CSV.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                zh = (row.get("zh") or "").strip()
                en = (row.get("en") or "").strip()
                if zh and en:
                    aliases[zh] = en
    return aliases


def _load_fx_patterns() -> list[tuple[str, str, str, int]]:
    patterns: list[tuple[str, str, str, int]] = []
    if FX_PATTERN_CSV.is_file():
        with FX_PATTERN_CSV.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                zh = (row.get("zh") or "").strip()
                en = (row.get("en") or "").strip()
                slot = (row.get("slot") or "fx").strip()
                try:
                    priority = int((row.get("priority") or "0").strip())
                except ValueError:
                    priority = 0
                if zh and en:
                    patterns.append((zh, en, slot, priority))
    if not patterns:
        patterns.extend(MIN_FX_PATTERN_FALLBACK)
    patterns.sort(key=lambda item: (item[3], len(item[0])))
    return patterns


def _load_best_zh_entries(matcher: GlossaryMatcher) -> dict[str, GlossaryEntry]:
    """同一中文只保留最高 priority 的英文（user_overrides 优先于 UCS 脏数据）。"""
    best: dict[str, GlossaryEntry] = {}
    best_pri: dict[str, int] = {}
    conn = sqlite3.connect(matcher.db_path)
    try:
        rows = conn.execute(
            """
            SELECT en, zh, term_type, action, priority
            FROM glossary
            WHERE zh IS NOT NULL AND zh != '' AND action = 'translate'
            ORDER BY priority DESC, LENGTH(zh) DESC
            """
        )
        for en, zh, term_type, action, priority in rows:
            zh = zh.strip()
            if not zh or not en:
                continue
            pri = int(priority or 0)
            if zh not in best or pri > best_pri[zh]:
                best[zh] = GlossaryEntry(
                    en=en.strip(),
                    zh=zh,
                    term_type=term_type or "",
                    action=action or "translate",
                )
                best_pri[zh] = pri
    finally:
        conn.close()
    return best


def build_compose_index(matcher: GlossaryMatcher) -> list[tuple[str, GlossaryEntry]]:
    """最长优先的中文片段索引（含口语别名、词干）。"""
    seen: set[str] = set()
    index: list[tuple[str, GlossaryEntry]] = []

    def add(zh: str, en: str, term_type: str = "oral", force: bool = False) -> None:
        if not zh or not en:
            return
        if zh in seen and not force:
            return
        if force and zh in seen:
            index[:] = [(z, e) for z, e in index if z != zh]
        seen.add(zh)
        index.append(
            (
                zh,
                GlossaryEntry(en=en, zh=zh, term_type=term_type, action="translate"),
            )
        )

    for zh_text, entry in _load_best_zh_entries(matcher).items():
        if not entry.en:
            continue
        for variant in _split_zh_variants(zh_text):
            add(variant, entry.en, entry.term_type)
            for suffix in ("声", "音", "感", "的"):
                if variant.endswith(suffix) and len(variant) > len(suffix) + 1:
                    add(variant[: -len(suffix)], entry.en, entry.term_type)

    for zh, en in _load_oral_aliases().items():
        add(zh, en, "oral", force=True)

    for zh, en, slot, _priority in _load_fx_patterns():
        add(zh, en, f"fx_{slot}", force=True)

    index.sort(key=lambda item: len(item[0]), reverse=True)
    return index


def _zh_char_count(text: str) -> int:
    return sum(1 for c in text if "\u4e00" <= c <= "\u9fff")


def _append_token(parts: list[str], token: str) -> bool:
    token = _title_fx_token(token.strip())
    if not token:
        return False
    if parts and parts[-1].lower() == token.lower():
        return False
    parts.append(token)
    return True


def _title_fx_token(token: str) -> str:
    upper_words = {"FX", "SFX", "UCS", "BB", "DS"}
    words = token.split()
    titled: list[str] = []
    for word in words:
        if word.upper() in upper_words:
            titled.append(word.upper())
        elif word.isupper() and any(c.isdigit() for c in word):
            titled.append(word)
        else:
            titled.append(word[:1].upper() + word[1:].lower())
    return " ".join(titled)


def compose_zh_to_en_debug(
    text: str, matcher: GlossaryMatcher
) -> tuple[str, ComposeDiagnostics]:
    """
    从中文描述组装空格分隔的英文 FX 关键词。
    未识别字符跳过，整句不送 NLLB 碎块（避免幻觉）。
    """
    if not text.strip():
        return "", ComposeDiagnostics(text="", glossary_hits=0, coverage=0.0)

    text = normalize_fxname_input(text)
    if not text:
        return "", ComposeDiagnostics(text="", glossary_hits=0, coverage=0.0)

    index = build_compose_index(matcher)
    parts: list[str] = []
    hits = 0
    covered_zh = 0
    content_zh = 0
    unknown: list[str] = []
    unknown_buf: list[str] = []
    matched_terms: list[dict[str, str | int]] = []
    slot_terms: list[SlotTerm] = []
    group_id = 0
    i = 0
    n = len(text)

    def flush_unknown() -> None:
        if unknown_buf:
            unknown.append("".join(unknown_buf))
            unknown_buf.clear()

    while i < n:
        if text[i].isspace() or PUNCT.match(text[i]):
            flush_unknown()
            i += 1
            continue

        word_m = ASCII_WORD.match(text, i)
        if word_m:
            flush_unknown()
            token = word_m.group(0)
            _append_token(parts, token)
            slot_terms.extend(
                split_slot_terms(token, infer_slot(token), source="ascii", group=group_id)
            )
            group_id += 1
            i = word_m.end()
            continue

        skipped = False
        for fp in sorted(FILLER_PHRASES, key=len, reverse=True):
            if text.startswith(fp, i):
                flush_unknown()
                i += len(fp)
                skipped = True
                break
        if skipped:
            continue

        if text[i] in FILLER_CHARS:
            flush_unknown()
            i += 1
            continue

        matched = False
        for zh, entry in index:
            if zh == "门" and not _is_isolated_zh_term(text, i, len(zh)):
                continue
            if text.startswith(zh, i):
                flush_unknown()
                token = entry.en.strip()
                if _append_token(parts, token):
                    hits += 1
                slot = infer_slot(token, entry.term_type)
                slot_terms.extend(
                    split_slot_terms(token, slot, source="compose", group=group_id)
                )
                group_id += 1
                zh_len = _zh_char_count(zh)
                covered_zh += zh_len
                content_zh += zh_len
                matched_terms.append(
                    {
                        "zh": zh,
                        "en": token,
                        "type": entry.term_type,
                        "slot": slot,
                        "start": i,
                        "end": i + len(zh),
                    }
                )
                i += len(zh)
                matched = True
                break

        if not matched:
            if "\u4e00" <= text[i] <= "\u9fff":
                content_zh += 1
                unknown_buf.append(text[i])
            else:
                flush_unknown()
            i += 1

    flush_unknown()
    coverage = covered_zh / content_zh if content_zh else 0.0
    diagnostics = ComposeDiagnostics(
        text=" ".join(parts),
        glossary_hits=hits,
        coverage=coverage,
        unknown_zh=unknown,
        matched_terms=matched_terms,
        slots=slot_terms,
    )
    return diagnostics.text, diagnostics


def _is_isolated_zh_term(text: str, start: int, length: int) -> bool:
    before = text[start - 1] if start > 0 else ""
    after_idx = start + length
    after = text[after_idx] if after_idx < len(text) else ""
    return not ZH_CHAR_RE.match(before) and not ZH_CHAR_RE.match(after)


def compose_zh_to_en(text: str, matcher: GlossaryMatcher) -> tuple[str, int]:
    composed, diagnostics = compose_zh_to_en_debug(text, matcher)
    return composed, diagnostics.glossary_hits


def compose_coverage(text: str, matcher: GlossaryMatcher) -> float:
    """粗略估计术语表对中文字符的覆盖率。"""
    _, diagnostics = compose_zh_to_en_debug(text, matcher)
    return diagnostics.coverage
