"""用最新 translator 后端重跑「模拟测试报告」的 150 条中文输入（纯中→英 FXName）。

输出：
- docs/模拟测试报告/模拟测试结果.csv  覆盖为最新后端结果
- 控制台打印：AI(NLLB) 使用统计、来源分布、与旧基准对照
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "translator"))

from translator import api  # noqa: E402

REPORT_DIR = ROOT / "docs" / "模拟测试报告"
SRC_CSV = REPORT_DIR / "模拟测试结果.csv"
OUT_CSV = REPORT_DIR / "模拟测试结果.csv"


def read_inputs() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with SRC_CSV.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            rows.append(row)
    return rows


def classify_sources(traces) -> tuple[list[str], bool, list[str]]:
    """返回 (每token来源列表, 是否用到NLLB, unknown的中文token)。"""
    sources: list[str] = []
    used_nllb = False
    unknowns: list[str] = []
    for t in traces:
        dec = t.decision or ""
        if t.kind == "ascii":
            sources.append("protected")
            continue
        if dec == "dropped_stop":
            continue
        base = dec.split("+", 1)[0]  # 'nllb+snap...' -> 'nllb'
        if base == "unknown" or not t.translated:
            unknowns.append(t.source_text)
            sources.append("unknown")
            continue
        sources.append(base)
        if base == "nllb":
            used_nllb = True
    return sources, used_nllb, unknowns


def main() -> None:
    rows = read_inputs()
    out_rows: list[dict[str, str]] = []
    src_counter: Counter[str] = Counter()
    nllb_rows: list[tuple[str, str, str, list[str]]] = []  # id, input, output, nllb_tokens
    unknown_rows: list[tuple[str, str, list[str]]] = []
    changed_rows: list[tuple[str, str, str, str]] = []  # id, input, old, new

    for row in rows:
        rid = row.get("id", "")
        group = row.get("组别", "")
        text = row.get("测试词/短句", "")
        old_out = row.get("结果", "")

        res = api.to_fxname(text)
        new_out = res.text
        sources, used_nllb, unknowns = classify_sources(res.detail.traces)
        src_counter.update(sources)

        # 找出具体走 NLLB 的 token
        nllb_tokens = [
            t.source_text for t in res.detail.traces
            if t.kind == "zh" and (t.decision or "").split("+", 1)[0] == "nllb"
        ]
        if used_nllb:
            nllb_rows.append((rid, text, new_out, nllb_tokens))
        if unknowns:
            unknown_rows.append((rid, text, unknowns))
        if new_out != old_out:
            changed_rows.append((rid, text, old_out, new_out))

        out_rows.append({
            "id": rid,
            "组别": group,
            "方向": "中→英",
            "测试词/短句": text,
            "结果(最新后端)": new_out,
            "AI(NLLB)是否参与": "是" if used_nllb else "否",
            "NLLB token": ";".join(nllb_tokens),
            "unknown未译token": ";".join(unknowns),
            "每token来源": " ".join(sources),
        })

    fieldnames = [
        "id", "组别", "方向", "测试词/短句", "结果(最新后端)",
        "AI(NLLB)是否参与", "NLLB token", "unknown未译token", "每token来源",
    ]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    total = len(rows)
    print("=" * 60)
    print(f"总条数: {total}")
    print(f"用到 AI(NLLB) 的条目数: {len(nllb_rows)} / {total}")
    print(f"含 unknown 未译 token 的条目数: {len(unknown_rows)} / {total}")
    print(f"与旧基准结果不同的条目数: {len(changed_rows)} / {total}")
    print("-" * 60)
    print("每个 token 的来源分布:")
    for src, n in src_counter.most_common():
        print(f"  {src:12s}: {n}")
    print("-" * 60)
    if nllb_rows:
        print("【用到 NLLB 的条目明细】")
        for rid, text, out, toks in nllb_rows:
            print(f"  {rid}  {text}  ->  {out}   (NLLB token: {','.join(toks)})")
    else:
        print("【NLLB 使用明细】150 条里没有任何一个 token 走到 NLLB 兜底。")
    print("-" * 60)
    if unknown_rows:
        print("【含 unknown 未译 token 的条目】")
        for rid, text, unk in unknown_rows:
            print(f"  {rid}  {text}   (unknown: {','.join(unk)})")
    print("-" * 60)
    print(f"NLLB 是否曾被加载(单例已实例化): {api.nllb._translator is not None}")
    print("=" * 60)


if __name__ == "__main__":
    main()
