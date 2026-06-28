"""把 BOOM 全库英文 FXName 回译成中文，作为模式1 的测试输入（可长跑、可断点续跑）。

我们没有大规模真实中文，但有真实英文 FXName（目标）。回译造测试能在全库规模上
系统暴露「哪些 BOOM 英文我们的管线复现不了」。

provider:
- nllb（默认）: 本地 NLLB en->zh，零成本、离线，适合无人值守长跑
- openai      : 任意 OpenAI 兼容便宜 API（更自然的中文），读环境变量：
                TRANSLATOR_API_BASE / TRANSLATOR_API_KEY / TRANSLATOR_API_MODEL

输出（断点续跑）：translator/data/boom_zh_testcases.csv  (en, zh, provider)

用法：
    python tools/gen_zh_testcases.py --limit 80000
    python tools/gen_zh_testcases.py --provider openai --limit 80000
"""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BOOM_INDEX = ROOT / "glossary" / "boom_style_index.sqlite"
OUT_PATH = ROOT / "translator" / "data" / "boom_zh_testcases.csv"


def load_done() -> set[str]:
    done: set[str] = set()
    if OUT_PATH.exists():
        with OUT_PATH.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("en"):
                    done.add(row["en"])
    return done


def fetch_fxnames(limit: int | None, offset: int) -> list[str]:
    conn = sqlite3.connect(f"file:{BOOM_INDEX}?mode=ro", uri=True)
    sql = ("SELECT DISTINCT fx_name FROM fx_records "
           "WHERE fx_name IS NOT NULL AND TRIM(fx_name) <> '' ORDER BY fx_name")
    rows = [r[0] for r in conn.execute(sql)]
    conn.close()
    rows = rows[offset:]
    if limit:
        rows = rows[:limit]
    return rows


def _nllb_backtranslate(text: str) -> str:
    from translator import nllb

    return nllb.en2zh(text)


def _api_backtranslate(text: str, base: str, key: str, model: str) -> str:
    import requests

    resp = requests.post(
        f"{base.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content":
                 "你是音效命名翻译助手。把给定的英文音效名翻成自然、口语化的中文短语，"
                 "保留型号码/数字/序号原样。只输出中文，不要解释。"},
                {"role": "user", "content": text},
            ],
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["nllb", "openai"], default="nllb")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--flush-every", type=int, default=50)
    args = ap.parse_args()

    base = os.environ.get("TRANSLATOR_API_BASE", "")
    key = os.environ.get("TRANSLATOR_API_KEY", "")
    model = os.environ.get("TRANSLATOR_API_MODEL", "")
    if args.provider == "openai" and not (base and key and model):
        print("错误：openai provider 需设置 TRANSLATOR_API_BASE/KEY/MODEL 环境变量")
        sys.exit(1)

    done = load_done()
    targets = [e for e in fetch_fxnames(args.limit, args.offset) if e not in done]
    print(f"待回译: {len(targets)}（已完成 {len(done)}）provider={args.provider}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    new_file = not OUT_PATH.exists()
    handle = OUT_PATH.open("a", encoding="utf-8", newline="")
    writer = csv.writer(handle)
    if new_file:
        writer.writerow(["en", "zh", "provider"])

    start = time.time()
    ok = 0
    try:
        for i, en in enumerate(targets):
            try:
                if args.provider == "nllb":
                    zh = _nllb_backtranslate(en)
                else:
                    zh = _api_backtranslate(en, base, key, model)
            except Exception as exc:
                print(f"  [skip] {en!r}: {exc}")
                continue
            if zh:
                writer.writerow([en, zh, args.provider])
                ok += 1
            if (i + 1) % args.flush_every == 0:
                handle.flush()
                rate = (i + 1) / max(time.time() - start, 1e-6)
                print(f"  ...{i + 1}/{len(targets)} ok={ok} {rate:.1f}/s")
    finally:
        handle.flush()
        handle.close()
    print(f"完成：新增 {ok} 条 -> {OUT_PATH}  ({time.time() - start:.1f}s)")


if __name__ == "__main__":
    main()
