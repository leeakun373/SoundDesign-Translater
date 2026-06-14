#!/usr/bin/env python3
"""合并 UCS 底库与 user_overrides，生成 audio_glossary.sqlite。"""

from __future__ import annotations

import csv
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

GLOSSARY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = GLOSSARY_DIR.parent
SOURCES_DIR = GLOSSARY_DIR / "sources"
DEFAULT_DB = GLOSSARY_DIR / "audio_glossary.sqlite"
OVERRIDES_CSV = GLOSSARY_DIR / "user_overrides.csv"

MY_KEYWORD_CSV = Path(
    os.environ.get("GLOSSARY_MY_KEYWORD", str(SOURCES_DIR / "MyKeyWordV1.csv"))
)
UCS_CATID_CSV = Path(
    os.environ.get("GLOSSARY_UCS_CATID", str(SOURCES_DIR / "ucs_catid_list.csv"))
)
UCS_OFFICIAL_CSV = Path(
    os.environ.get("GLOSSARY_UCS_OFFICIAL", str(SOURCES_DIR / "ucs_categorylist.csv"))
)

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS glossary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    en TEXT NOT NULL,
    en_norm TEXT NOT NULL,
    zh TEXT,
    term_type TEXT NOT NULL,
    action TEXT NOT NULL,
    source TEXT,
    note TEXT,
    priority INTEGER NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_glossary_en_norm ON glossary(en_norm);

CREATE TABLE IF NOT EXISTS catids (
    catid TEXT PRIMARY KEY
);
"""

# 优先级：数值越大越优先（同 en_norm 时保留高优先级）
PRIORITY = {
    "user_overrides": 100,
    "MyKeyWordV1": 80,
    "ucs_catid_list": 60,
    "ucs_official": 40,
}


@dataclass
class TermEntry:
    en: str
    zh: str
    term_type: str
    action: str
    source: str
    note: str = ""
    priority: int = 0

    @property
    def en_norm(self) -> str:
        return self.en.strip().lower()


def _split_csv_list(value: str) -> list[str]:
    if not value or not value.strip():
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _split_zh_list(value: str) -> list[str]:
    if not value or not value.strip():
        return []
    parts: list[str] = []
    for chunk in value.replace("、", ",").split(","):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts


class GlossaryBuilder:
    def __init__(self) -> None:
        self._entries: dict[str, TermEntry] = {}
        self._catids: set[str] = set()

    def add(self, entry: TermEntry) -> None:
        key = entry.en_norm
        if not key:
            return
        existing = self._entries.get(key)
        if existing is None or entry.priority >= existing.priority:
            self._entries[key] = entry
        if entry.term_type == "catid" or entry.action == "never_translate" and entry.term_type == "catid":
            self._catids.add(entry.en.strip())

    def add_catid(self, catid: str, source: str) -> None:
        catid = catid.strip()
        if not catid:
            return
        self._catids.add(catid)
        self.add(
            TermEntry(
                en=catid,
                zh="",
                term_type="catid",
                action="never_translate",
                source=source,
                note="UCS CatID",
                priority=PRIORITY.get(source, 50),
            )
        )

    def load_overrides(self) -> int:
        if not OVERRIDES_CSV.is_file():
            return 0
        count = 0
        with OVERRIDES_CSV.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                en = (row.get("en") or "").strip()
                if not en:
                    continue
                self.add(
                    TermEntry(
                        en=en,
                        zh=(row.get("zh") or "").strip(),
                        term_type=(row.get("term_type") or "user_override").strip(),
                        action=(row.get("action") or "translate").strip(),
                        source="user_overrides",
                        note=(row.get("note") or "").strip(),
                        priority=PRIORITY["user_overrides"],
                    )
                )
                count += 1
        return count

    def load_my_keyword(self) -> int:
        if not MY_KEYWORD_CSV.is_file():
            print(f"[skip] MyKeyWord not found: {MY_KEYWORD_CSV}")
            return 0
        count = 0
        with MY_KEYWORD_CSV.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                en = (row.get("Keyword") or "").strip()
                zh = (row.get("Keyword(Trans)") or "").strip()
                if en and zh:
                    self.add(
                        TermEntry(
                            en=en,
                            zh=zh,
                            term_type="keyword",
                            action="translate",
                            source="MyKeyWordV1",
                            priority=PRIORITY["MyKeyWordV1"],
                        )
                    )
                    count += 1
        return count

    def _load_ucs_row(self, row: dict, source: str, priority: int) -> int:
        count = 0
        catid = (row.get("CatID") or "").strip()
        if catid:
            self.add_catid(catid, source)
            count += 1

        category = (row.get("Category") or "").strip()
        category_zh = (row.get("Category_zh") or "").strip()
        if category and category_zh:
            self.add(
                TermEntry(
                    en=category,
                    zh=category_zh,
                    term_type="category",
                    action="translate",
                    source=source,
                    priority=priority,
                )
            )
            count += 1

        subcategory = (row.get("SubCategory") or "").strip()
        subcategory_zh = (row.get("SubCategory_zh") or "").strip()
        if subcategory and subcategory_zh:
            self.add(
                TermEntry(
                    en=subcategory,
                    zh=subcategory_zh,
                    term_type="subcategory",
                    action="translate",
                    source=source,
                    priority=priority,
                )
            )
            count += 1

        fallback_zh = subcategory_zh or category_zh
        for syn in _split_csv_list(row.get("Synonyms - Comma Separated") or ""):
            if syn and fallback_zh:
                self.add(
                    TermEntry(
                        en=syn,
                        zh=fallback_zh,
                        term_type="synonym",
                        action="translate",
                        source=source,
                        priority=priority - 1,
                    )
                )
                count += 1

        zh_syns = _split_zh_list(row.get("Synonyms_zh") or "")
        for zh_syn in zh_syns:
            if subcategory and zh_syn:
                self.add(
                    TermEntry(
                        en=subcategory,
                        zh=zh_syn,
                        term_type="synonym",
                        action="translate",
                        source=source,
                        note="Synonyms_zh alias",
                        priority=priority - 2,
                    )
                )
        return count

    def load_ucs_catid(self) -> int:
        if not UCS_CATID_CSV.is_file():
            print(f"[skip] ucs_catid_list not found: {UCS_CATID_CSV}")
            return 0
        count = 0
        with UCS_CATID_CSV.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                count += self._load_ucs_row(row, "ucs_catid_list", PRIORITY["ucs_catid_list"])
        return count

    def load_ucs_official(self) -> int:
        if not UCS_OFFICIAL_CSV.is_file():
            print(f"[skip] UCS official not found: {UCS_OFFICIAL_CSV}")
            return 0
        count = 0
        with UCS_OFFICIAL_CSV.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                count += self._load_ucs_row(row, "ucs_official", PRIORITY["ucs_official"])
        return count

    def write_sqlite(self, db_path: Path = DEFAULT_DB) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if db_path.exists():
            db_path.unlink()
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(SCHEMA_SQL)
            rows = [
                (
                    e.en,
                    e.en_norm,
                    e.zh or None,
                    e.term_type,
                    e.action,
                    e.source,
                    e.note or None,
                    e.priority,
                )
                for e in self._entries.values()
            ]
            conn.executemany(
                """
                INSERT INTO glossary (en, en_norm, zh, term_type, action, source, note, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.executemany(
                "INSERT OR IGNORE INTO catids (catid) VALUES (?)",
                [(c,) for c in sorted(self._catids)],
            )
            conn.commit()
        finally:
            conn.close()

    @property
    def stats(self) -> dict[str, int]:
        return {
            "entries": len(self._entries),
            "catids": len(self._catids),
        }


def build(db_path: Path = DEFAULT_DB) -> dict[str, int]:
    builder = GlossaryBuilder()
    print("Loading user_overrides...")
    n0 = builder.load_overrides()
    print("Loading MyKeyWordV1...")
    n1 = builder.load_my_keyword()
    print("Loading ucs_catid_list...")
    n2 = builder.load_ucs_catid()
    print("Loading UCS official...")
    n3 = builder.load_ucs_official()
    builder.write_sqlite(db_path)
    stats = builder.stats
    print(f"Written {stats['entries']} entries, {stats['catids']} catids -> {db_path}")
    print(f"  overrides={n0}, mykeyword={n1}, ucs={n2}, official={n3}")
    return stats


def main() -> None:
    import sys

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    build()
    from glossary.matcher import smoke_test

    smoke_test()


if __name__ == "__main__":
    main()
