#!/usr/bin/env python3
"""导出「未收录高频词」分批 CSV，供 AI 填译文、人工验收后写入 user_overrides.csv。"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_COMMERCIAL_DB = Path(
    os.environ.get("UCS_COMMERCIAL_DB", "")
) if os.environ.get("UCS_COMMERCIAL_DB") else None
GLOSSARY_DB = ROOT / "glossary" / "audio_glossary.sqlite"
OVERRIDES_CSV = ROOT / "glossary" / "user_overrides.csv"
BATCH_DIR = ROOT / "glossary" / "batches"

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-]*")
STOPWORDS = {
    "the", "and", "for", "with", "from", "wav", "mp3", "flac", "a", "an", "of", "in", "to",
    "com", "www", "http", "https", "ver", "v1", "v2",
    # 普通英文（非音效术语），避免占满批次
    "user", "very", "into", "quick", "object", "constant", "multiple", "distance",
    "this", "that", "these", "those", "your", "our", "their", "its", "are", "was", "were",
    "has", "have", "had", "not", "but", "can", "will", "would", "should", "could",
    # 批001/002 验收拒绝的普通英文
    "away", "positioned", "loud", "mid", "left", "like", "slowly", "right", "second",
    "some", "times", "two", "quickly", "handed", "putting", "filled", "behind",
    "heavily", "other", "then", "length", "size", "slightly", "various", "against",
    "men", "played", "bunch", "position", "normal", "remove", "throughout",
    # 批003 验收拒绝
    "using", "taking", "regular", "enabling", "disabling", "pointing", "element",
    "day", "brief", "simple", "order", "nearby", "wide", "creating", "character",
    "assembled", "occasional", "indirect", "dynamic", "direct", "filtered", "gaming",
}

# 明显是厂商码/CatID/设备码的启发式
VENDOR_LIKE = re.compile(r"^[A-Z]{2,6}$")
DEVICE_LIKE = re.compile(r"^[A-Z]{1,4}\d+[A-Z0-9]*$", re.I)
CATID_LIKE = re.compile(r"^[A-Z]{3,5}[A-Z][a-z]{3,5}$")  # ICEFric 类
LIB_PREFIX_LIKE = re.compile(r"^[a-z]{2,6}ck$|^[a-z]{2,5}ds$|^[a-z]{2,4}tg$", re.I)


def load_known_en(glossary_db: Path, overrides_csv: Path) -> set[str]:
    known: set[str] = set()
    if glossary_db.is_file():
        conn = sqlite3.connect(glossary_db)
        try:
            for (en,) in conn.execute("SELECT en FROM glossary"):
                if en:
                    known.add(en.strip().lower())
            for (catid,) in conn.execute("SELECT catid FROM catids"):
                if catid:
                    known.add(catid.strip().lower())
        finally:
            conn.close()
    if overrides_csv.is_file():
        with overrides_csv.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                en = (row.get("en") or "").strip()
                if en:
                    known.add(en.lower())
    return known


def guess_term_type(token: str) -> str:
    if CATID_LIKE.match(token):
        return "catid"
    if LIB_PREFIX_LIKE.match(token):
        return "device"
    if DEVICE_LIKE.match(token):
        return "device"
    if VENDOR_LIKE.match(token):
        return "vendor"
    if " " in token:
        return "keyword"
    return "keyword"


def guess_action(term_type: str) -> str:
    if term_type in ("catid", "vendor", "device"):
        return "never_translate"
    return "translate"


def collect_tokens(db_path: Path) -> Counter[str]:
    conn = sqlite3.connect(db_path)
    counter: Counter[str] = Counter()
    try:
        for filename, description in conn.execute(
            "SELECT filename, description FROM commercial_assets"
        ):
            text = f"{filename or ''} {description or ''}"
            for token in TOKEN_RE.findall(text):
                low = token.lower()
                if len(low) < 3 or low in STOPWORDS:
                    continue
                counter[low] += 1
            # 多词短语：从 filename 里抽 2~3 gram（仅空格分隔段内）
            for part in (filename or "").replace("_", " ").split():
                pass
    finally:
        conn.close()
    return counter


def dedupe_ranked_tokens(counter: Counter[str], known: set[str], min_count: int) -> list[tuple[str, int]]:
    """去重（小写唯一）+ 排除已收录 + 按频次降序。"""
    seen: set[str] = set()
    result: list[tuple[str, int]] = []
    for token, count in counter.most_common():
        key = token.lower()
        if key in seen or key in known or count < min_count:
            continue
        seen.add(key)
        # 保留原始最常见写法：这里用小写统一，便于 AI 处理；用户可在验收时改大小写
        result.append((token, count))
    return result


def write_batch(
    batch_index: int,
    items: list[tuple[str, int]],
    out_dir: Path,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"uncovered_batch_{batch_index:03d}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "en",
                "zh",
                "term_type",
                "action",
                "note",
                "count",
                "review_status",
            ],
        )
        writer.writeheader()
        for token, count in items:
            term_type = guess_term_type(token)
            action = guess_action(term_type)
            writer.writerow(
                {
                    "en": token,
                    "zh": "",
                    "term_type": term_type,
                    "action": action,
                    "note": f"freq={count};待填zh",
                    "count": count,
                    "review_status": "pending",
                }
            )
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="分批导出未收录高频词（去重+格式统一）")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_COMMERCIAL_DB,
        help="商业库 SQLite（可选，也可用环境变量 UCS_COMMERCIAL_DB）",
    )
    parser.add_argument("--glossary", type=Path, default=GLOSSARY_DB)
    parser.add_argument("--overrides", type=Path, default=OVERRIDES_CSV)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--batch-index", type=int, default=1, help="导出第几批（从1开始）")
    parser.add_argument("--min-count", type=int, default=20)
    parser.add_argument("--out-dir", type=Path, default=BATCH_DIR)
    args = parser.parse_args()

    if args.db is None or not args.db.is_file():
        raise SystemExit(
            "商业库未指定或不存在。请: --db path/to/ucs_assets.db\n"
            "或设置环境变量 UCS_COMMERCIAL_DB"
        )
    if not args.glossary.is_file():
        raise SystemExit(f"术语库不存在: {args.glossary}\n请先运行 build_glossary.bat")

    known = load_known_en(args.glossary, args.overrides)
    counter = collect_tokens(args.db)
    ranked = dedupe_ranked_tokens(counter, known, args.min_count)

    start = (args.batch_index - 1) * args.batch_size
    end = start + args.batch_size
    batch_items = ranked[start:end]

    if not batch_items:
        print(f"第 {args.batch_index} 批无数据（可能已导出完毕）")
        print(f"去重后候选总数: {len(ranked)}")
        return

    path = write_batch(args.batch_index, batch_items, args.out_dir)
    print(f"商业库 token 种类: {len(counter)}")
    print(f"已收录(含 overrides): {len(known)}")
    print(f"去重后未收录候选: {len(ranked)}")
    print(f"本批: 第 {args.batch_index} 批，{len(batch_items)} 条")
    print(f"已写入: {path}")
    print(f"频次范围: {batch_items[-1][1]} ~ {batch_items[0][1]}")


if __name__ == "__main__":
    main()
