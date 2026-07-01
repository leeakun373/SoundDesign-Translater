"""术语匹配：最长匹配、占位保护、查表。"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from translator.paths import AUDIO_GLOSSARY_DB

DEFAULT_DB = AUDIO_GLOSSARY_DB


class GlossaryNotFoundError(FileNotFoundError):
    """术语库 SQLite 不存在。"""


@dataclass(frozen=True)
class GlossaryEntry:
    en: str
    zh: str
    term_type: str
    action: str


@dataclass
class TextSegment:
    text: str
    entry: GlossaryEntry | None = None


class GlossaryMatcher:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DEFAULT_DB
        if not self.db_path.is_file():
            raise GlossaryNotFoundError(
                f"术语库不存在: {self.db_path}\n请先运行: python glossary/build_glossary.py"
            )
        self._entries_en: list[GlossaryEntry] = []
        self._entries_zh: list[tuple[str, GlossaryEntry]] = []
        self._catids: set[str] = set()
        self._never_translate: set[str] = set()
        self._by_en_norm: dict[str, GlossaryEntry] = {}
        self._load()

    def _load(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                """
                SELECT en, zh, term_type, action
                FROM glossary
                ORDER BY LENGTH(en) DESC
                """
            )
            for en, zh, term_type, action in cur.fetchall():
                entry = GlossaryEntry(
                    en=en,
                    zh=zh or "",
                    term_type=term_type or "",
                    action=action or "translate",
                )
                self._entries_en.append(entry)
                self._by_en_norm[en.strip().lower()] = entry
                if entry.zh:
                    self._entries_zh.append((entry.zh, entry))
                if action == "never_translate":
                    self._never_translate.add(en.strip())
                    self._never_translate.add(en.strip().lower())

            cur = conn.execute("SELECT catid FROM catids")
            self._catids = {row[0] for row in cur.fetchall()}
        finally:
            conn.close()
        self._entries_zh.sort(key=lambda x: len(x[0]), reverse=True)

    def iter_zh_translate_entries(self) -> list[tuple[str, GlossaryEntry]]:
        """中→英组装：全部带译文条目（不过滤 protect 规则）。"""
        seen: set[tuple[str, str]] = set()
        out: list[tuple[str, GlossaryEntry]] = []
        for zh_text, entry in self._entries_zh:
            if entry.action != "translate" or not entry.en or not zh_text:
                continue
            key = (zh_text, entry.en.lower())
            if key in seen:
                continue
            seen.add(key)
            out.append((zh_text, entry))
        return out

    @property
    def catids(self) -> set[str]:
        return set(self._catids)

    def lookup_en(self, token: str) -> GlossaryEntry | None:
        return self._by_en_norm.get(token.strip().lower())

    def is_catid(self, token: str) -> bool:
        return token.strip() in self._catids

    def is_never_translate(self, token: str) -> bool:
        t = token.strip()
        if t in self._never_translate or t.lower() in self._never_translate:
            return True
        entry = self.lookup_en(t)
        return entry is not None and entry.action == "never_translate"

    def translate_token(self, token: str, to_zh: bool) -> str | None:
        """英→中 或 中→英 单词级查表。"""
        entry = self.lookup_en(token)
        if entry and entry.action == "translate" and entry.zh:
            return entry.zh if to_zh else entry.en
        if not to_zh:
            for zh_text, ent in self._entries_zh:
                if zh_text == token.strip() and ent.en:
                    return ent.en
        return None

    def _eligible_for_protect(self, entry: GlossaryEntry) -> bool:
        """句子保护只用高置信条目，避免同义词把短词打碎。"""
        if entry.action != "translate" or not entry.zh:
            return False
        if entry.term_type in ("keyword", "user_override"):
            return True
        if " " in entry.en:
            return True
        return len(entry.en) >= 8

    def _match_pattern(self, en: str) -> re.Pattern[str]:
        if " " in en.strip():
            return re.compile(re.escape(en.strip()), re.IGNORECASE)
        return re.compile(r"\b" + re.escape(en.strip()) + r"\b", re.IGNORECASE)

    def segment_for_translation(
        self, text: str, src_is_zh: bool
    ) -> tuple[list[TextSegment], int]:
        """将句子切成「术语段 + 普通段」，术语段不经 NLLB 直接替换。"""
        matches: list[tuple[int, int, GlossaryEntry]] = []

        if src_is_zh:
            for zh_text, entry in self._entries_zh:
                if not self._eligible_for_protect(entry):
                    continue
                start = 0
                while True:
                    idx = text.find(zh_text, start)
                    if idx == -1:
                        break
                    matches.append((idx, idx + len(zh_text), entry))
                    start = idx + len(zh_text)
        else:
            for entry in sorted(
                [e for e in self._entries_en if self._eligible_for_protect(e)],
                key=lambda e: len(e.en),
                reverse=True,
            ):
                for match in self._match_pattern(entry.en).finditer(text):
                    matches.append((match.start(), match.end(), entry))

        matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))
        selected: list[tuple[int, int, GlossaryEntry]] = []
        for start, end, entry in matches:
            if any(not (end <= s or start >= e) for s, e, _ in selected):
                continue
            selected.append((start, end, entry))
        selected.sort(key=lambda item: item[0])

        segments: list[TextSegment] = []
        hits = 0
        cursor = 0
        for start, end, entry in selected:
            if start > cursor:
                segments.append(TextSegment(text[cursor:start], None))
            segments.append(TextSegment(text[start:end], entry))
            hits += 1
            cursor = end
        if cursor < len(text):
            segments.append(TextSegment(text[cursor:], None))
        if not segments:
            segments.append(TextSegment(text, None))
        return segments, hits

    def force_replace_en_to_zh(self, text: str) -> tuple[str, int]:
        """在中文输出中，将残留的英文术语强制替换为中文。"""
        result = text
        hits = 0
        sorted_entries = sorted(
            [e for e in self._entries_en if e.action == "translate" and e.zh],
            key=lambda e: len(e.en),
            reverse=True,
        )
        for entry in sorted_entries:
            pattern = re.compile(re.escape(entry.en), re.IGNORECASE)
            if pattern.search(result):
                result = pattern.sub(entry.zh, result)
                hits += 1
        return result, hits


def smoke_test(db_path: Path | None = None) -> None:
    matcher = GlossaryMatcher(db_path)
    assert matcher.lookup_en("Room Tone") is not None or matcher.lookup_en("room tone")
    rt = matcher.lookup_en("Room Tone") or matcher._by_en_norm.get("room tone")
    assert rt is not None, "Room Tone missing"
    assert rt.zh == "房间底噪", f"Room Tone zh expected 房间底噪, got {rt.zh}"
    assert matcher.is_catid("ICEFric"), "ICEFric should be catid"
    assert matcher.is_never_translate("ASO"), "ASO should be never_translate"
    segs, hits = matcher.segment_for_translation("Room tone of empty office", src_is_zh=False)
    assert hits >= 1
    assert any(s.entry and s.entry.en.lower() == "room tone" for s in segs)
    print("glossary smoke_test: OK")


if __name__ == "__main__":
    smoke_test()
