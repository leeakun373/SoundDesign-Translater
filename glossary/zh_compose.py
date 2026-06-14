"""中文描述 → 英文 FX 名/关键词：术语表最长匹配组装，不依赖 NLLB 碎句。"""

from __future__ import annotations

import csv
import re
import sqlite3
from pathlib import Path

from glossary.matcher import GlossaryEntry, GlossaryMatcher

ORAL_CSV = Path(__file__).resolve().parent / "zh_oral_aliases.csv"

# 跳过虚词/量词/口语连接（不参与输出）
FILLER_CHARS = frozenset("的了下着过在与和及或就还把被让给跟从向以很更最里来去到")
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
    }
    if ORAL_CSV.is_file():
        with ORAL_CSV.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                zh = (row.get("zh") or "").strip()
                en = (row.get("en") or "").strip()
                if zh and en:
                    aliases[zh] = en
    return aliases


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

    index.sort(key=lambda item: len(item[0]), reverse=True)
    return index


def compose_zh_to_en(text: str, matcher: GlossaryMatcher) -> tuple[str, int]:
    """
    从中文描述组装空格分隔的英文 FX 关键词。
    未识别字符跳过，整句不送 NLLB 碎块（避免幻觉）。
    """
    if not text.strip():
        return "", 0

    index = build_compose_index(matcher)
    parts: list[str] = []
    hits = 0
    i = 0
    n = len(text)

    while i < n:
        if text[i].isspace() or PUNCT.match(text[i]):
            i += 1
            continue

        word_m = ASCII_WORD.match(text, i)
        if word_m:
            token = word_m.group(0)
            if token and (not parts or parts[-1].lower() != token.lower()):
                parts.append(token)
            i = word_m.end()
            continue

        skipped = False
        for fp in sorted(FILLER_PHRASES, key=len, reverse=True):
            if text.startswith(fp, i):
                i += len(fp)
                skipped = True
                break
        if skipped:
            continue

        if text[i] in FILLER_CHARS:
            i += 1
            continue

        matched = False
        for zh, entry in index:
            if text.startswith(zh, i):
                token = entry.en.strip()
                if token and (not parts or parts[-1].lower() != token.lower()):
                    parts.append(token)
                    hits += 1
                i += len(zh)
                matched = True
                break

        if not matched:
            i += 1

    return " ".join(parts), hits


def compose_coverage(text: str, matcher: GlossaryMatcher) -> float:
    """粗略估计术语表对中文字符的覆盖率。"""
    if not text.strip():
        return 0.0
    index = build_compose_index(matcher)
    zh_chars = [c for c in text if "\u4e00" <= c <= "\u9fff"]
    if not zh_chars:
        return 0.0
    covered = 0
    i = 0
    while i < len(text):
        if text[i] not in zh_chars and not ("\u4e00" <= text[i] <= "\u9fff"):
            i += 1
            continue
        matched = False
        for zh, _ in index:
            if text.startswith(zh, i):
                covered += len(zh)
                i += len(zh)
                matched = True
                break
        if not matched:
            if "\u4e00" <= text[i] <= "\u9fff" and text[i] not in FILLER_CHARS:
                pass
            i += 1
    return covered / len(zh_chars)
