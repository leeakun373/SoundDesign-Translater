"""按「价值」给 BOOM 各库排精翻批次，并导出可直接填的精翻模板。

价值直觉：
  - 高价值 = 用高频通用词汇 + 体量够 → 翻了能教会管线最多「可迁移」的受控词汇
  - 低价值 = 稀有一次性组合 / 专有名词多（DS 特种库）→ 学不到通用词，缓翻

每库指标：
  records           条数
  distinct_tokens   去重英文词数
  reuse             该库词汇的「全局复用度」(各 token 全局词频的几何均值)，越高越通用
  rare_ratio        稀有词占比(全局freq<=2)，越高越一次性
  value             排序分 = reuse * log(records)，rare_ratio 高则惩罚

用法：
  python tools/rank_boom_batches.py                      # 只出排序报告
  python tools/rank_boom_batches.py --export 8 --rows 400  # 导出前8个高价值库的精翻模板(每库最多400行)
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "glossary" / "boom_style_index.sqlite"
OUT_DIR = ROOT / "docs" / "训练数据" / "精确翻译"

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z]+")
# 文件名里的库代码/编号噪声（不计入词汇价值）
_CODE_RE = re.compile(r"^\d|^[a-z]{1,4}\d", re.I)
STOP = {"the", "a", "an", "of", "and", "to", "with", "in", "on", "at", "for", "wav"}


def fx_text(fx_name, filename) -> str:
    """取干净英文：优先 fx_name；否则用文件名去扩展名/库代码。"""
    if fx_name and fx_name.strip():
        return fx_name.strip()
    if not filename:
        return ""
    stem = re.sub(r"\.(wav|aif|aiff|flac|mp3)$", "", filename.strip(), flags=re.I)
    return stem


def good_tokens(text: str, gfreq: dict[str, int]) -> list[str]:
    out = []
    for w in _WORD_RE.findall(text.lower()):
        if w in STOP or _CODE_RE.match(w) or len(w) < 2:
            continue
        out.append(w)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", type=int, default=0, help="导出前 N 个高价值库的精翻模板")
    ap.add_argument("--rows", type=int, default=400, help="每库导出最多多少行")
    args = ap.parse_args()

    c = sqlite3.connect(str(DB))
    gfreq = {t: f for t, f in c.execute("select token, freq from tokens")}

    libs: dict[str, dict] = defaultdict(lambda: {
        "records": 0, "fxname_rows": 0, "tokens": Counter(), "rows": []
    })
    # 只用「有干净英文 fx_name」的记录：这些才精翻得了（英->中由 AI 补）。
    # 跳过 BOOM ONE 中文目录（垃圾机翻，无英文原文）。
    for fx_name, filename, library, source_file in c.execute(
        "select fx_name, filename, library, source_file from fx_records"
    ):
        if source_file and "BOOM ONE" in source_file:
            continue
        if not (fx_name and fx_name.strip()):
            continue
        lib = (library or "(unknown)").strip()
        d = libs[lib]
        d["records"] += 1
        d["fxname_rows"] += 1
        d["tokens"].update(good_tokens(fx_name, gfreq))
        if len(d["rows"]) < 5000:
            d["rows"].append((filename or "", fx_name.strip()))

    ranked = []
    for lib, d in libs.items():
        toks = d["tokens"]
        if not toks:
            continue
        freqs = [gfreq.get(t, 1) for t in toks]
        reuse = math.exp(sum(math.log(f) for f in freqs) / len(freqs))  # 几何均值
        rare = sum(1 for f in freqs if f <= 2) / len(freqs)
        value = reuse * math.log(d["records"] + 1) * (1 - 0.5 * rare)
        ranked.append({
            "library": lib,
            "records": d["records"],
            "distinct_tokens": len(toks),
            "reuse": round(reuse, 1),
            "rare_ratio": round(rare, 2),
            "value": round(value, 1),
        })
    ranked.sort(key=lambda r: -r["value"])

    print(f"{'#':>3} {'value':>7} {'reuse':>6} {'rare':>5} {'recs':>6}  library")
    for i, r in enumerate(ranked, 1):
        print(f"{i:>3} {r['value']:>7.1f} {r['reuse']:>6.1f} {r['rare_ratio']:>5.2f} "
              f"{r['records']:>6}  {r['library']}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "_批次优先级.json").write_text(
        json.dumps(ranked, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.export:
        idx_lines = ["# 精翻批次优先级（高价值先翻）\n",
                     "| 批次 | 价值 | 复用度 | 稀有占比 | 条数 | 库 | 模板文件 |",
                     "|---|---|---|---|---|---|---|"]
        for i, r in enumerate(ranked[: args.export], 1):
            lib = r["library"]
            safe = re.sub(r"[^\w\u4e00-\u9fff]+", "_", lib).strip("_")[:40]
            fn = f"{i:02d}_{safe}.csv"
            rows = libs[lib]["rows"][: args.rows]
            with (OUT_DIR / fn).open("w", encoding="utf-8-sig", newline="") as h:
                w = csv.writer(h)
                w.writerow(["完整原始名字", "原FXName", "中文翻译"])
                for filename, fx_name in rows:
                    # 没有 fx_name 的库：把文件名当 fx 来源，AI 仍可据此翻
                    w.writerow([filename, fx_name, ""])
            idx_lines.append(
                f"| {i:02d} | {r['value']:.0f} | {r['reuse']:.0f} | {r['rare_ratio']:.2f} "
                f"| {len(rows)} | {lib} | `{fn}` |")
        (OUT_DIR / "_批次优先级.md").write_text("\n".join(idx_lines), encoding="utf-8")
        print(f"\n已导出前 {args.export} 个库模板 -> {OUT_DIR}")


if __name__ == "__main__":
    main()
