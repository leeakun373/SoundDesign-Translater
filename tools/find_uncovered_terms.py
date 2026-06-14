#!/usr/bin/env python3
"""从 UCSRenamer 商业库挖掘高频但未收录的英文词。"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_DB = os.environ.get("UCS_COMMERCIAL_DB")
GLOSSARY_DB = ROOT / "glossary" / "audio_glossary.sqlite"

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-]*")
STOPWORDS = {
    "the", "and", "for", "with", "from", "wav", "mp3", "flac", "a", "an", "of", "in", "to",
}


def load_glossary_terms(glossary_db: Path) -> set[str]:
    conn = sqlite3.connect(glossary_db)
    try:
        rows = conn.execute("SELECT en FROM glossary").fetchall()
    finally:
        conn.close()
    return {row[0].strip().lower() for row in rows if row[0]}


def collect_tokens(db_path: Path, limit_rows: int | None = None) -> Counter[str]:
    conn = sqlite3.connect(db_path)
    counter: Counter[str] = Counter()
    try:
        sql = "SELECT filename, description FROM commercial_assets"
        if limit_rows:
            sql += f" LIMIT {int(limit_rows)}"
        for filename, description in conn.execute(sql):
            text = f"{filename or ''} {description or ''}"
            for token in TOKEN_RE.findall(text):
                low = token.lower()
                if len(low) < 3 or low in STOPWORDS:
                    continue
                counter[low] += 1
    finally:
        conn.close()
    return counter


def main() -> None:
    parser = argparse.ArgumentParser(description="挖掘商业库中未收录的高频英文词")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(DEFAULT_DB) if DEFAULT_DB else None,
        help="商业库 SQLite（或环境变量 UCS_COMMERCIAL_DB）",
    )
    parser.add_argument("--glossary", type=Path, default=GLOSSARY_DB)
    parser.add_argument("--top", type=int, default=50)
    parser.add_argument("--min-count", type=int, default=20)
    parser.add_argument("--limit-rows", type=int, default=None)
    args = parser.parse_args()

    if args.db is None or not args.db.is_file():
        raise SystemExit(
            "商业库未指定或不存在。请: --db path/to/ucs_assets.db\n"
            "或设置环境变量 UCS_COMMERCIAL_DB"
        )
    if not args.glossary.is_file():
        raise SystemExit(f"术语库不存在: {args.glossary}\n请先运行 python glossary/build_glossary.py")

    known = load_glossary_terms(args.glossary)
    counter = collect_tokens(args.db, args.limit_rows)

    uncovered = [
        (token, count)
        for token, count in counter.most_common()
        if token not in known and count >= args.min_count
    ]

    print(f"扫描 token 数: {len(counter)}")
    print(f"术语库词条: {len(known)}")
    print(f"未覆盖高频词 (count>={args.min_count}, top {args.top}):")
    print("count\ttoken")
    for token, count in uncovered[: args.top]:
        print(f"{count}\t{token}")


if __name__ == "__main__":
    main()
