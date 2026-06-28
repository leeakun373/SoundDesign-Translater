"""全 BOOM 覆盖评测：跑回译测试集，对比真实英文 FXName，挖掘最差/缺失 token。

输入：translator/data/boom_zh_testcases.csv（由 gen_zh_testcases.py 生成）
输出：reports/boom_full_eval_*.md
      - token-F1 总览
      - 高频「缺失 gold token」（=覆盖缺口，最该补 fx_overrides）
      - 高频「多余 pred token」（=误译/噪声）

用法：
    python tools/eval_boom_full.py
    python tools/eval_boom_full.py --limit 20000
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from translator import fxname_mode  # noqa: E402

CASES = ROOT / "translator" / "data" / "boom_zh_testcases.csv"
REPORT_DIR = ROOT / "reports"

_TOK_RE = re.compile(r"[a-z0-9][a-z0-9+\-]*")
# 纯数字/序号不计入覆盖统计（不反映翻译能力）
_NUM_RE = re.compile(r"^\d+[a-z]?$")


def tokenize(text: str, drop_numeric: bool = True) -> list[str]:
    toks = _TOK_RE.findall((text or "").lower())
    if drop_numeric:
        toks = [t for t in toks if not _NUM_RE.match(t)]
    return toks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    if not CASES.exists():
        print(f"未找到测试集：{CASES}\n先运行 python tools/gen_zh_testcases.py")
        sys.exit(1)

    rows = []
    with CASES.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("en") and row.get("zh"):
                rows.append((row["en"], row["zh"]))
    if args.limit:
        rows = rows[: args.limit]

    n = len(rows)
    sum_p = sum_r = sum_f = 0.0
    exact = 0
    missing = Counter()   # gold 有、pred 没有（覆盖缺口）
    spurious = Counter()  # pred 有、gold 没有（噪声）
    worst: list[tuple[float, str, str, str]] = []

    start = time.time()
    for i, (en, zh) in enumerate(rows):
        gold = tokenize(en)
        pred = tokenize(fxname_mode.normalize(zh).output_fxname)
        gset, pset = set(gold), set(pred)
        if not gset:
            continue
        inter = len(gset & pset)
        p = inter / len(pset) if pset else 0.0
        r = inter / len(gset)
        f = 0.0 if (p + r) == 0 else 2 * p * r / (p + r)
        sum_p += p; sum_r += r; sum_f += f
        if gset == pset:
            exact += 1
        for t in gset - pset:
            missing[t] += 1
        for t in pset - gset:
            spurious[t] += 1
        worst.append((f, zh, en, fxname_mode.normalize(zh).output_fxname))
        if (i + 1) % 2000 == 0:
            print(f"  ...{i + 1}/{n} ({time.time() - start:.1f}s)")

    denom = max(n, 1)
    worst.sort(key=lambda x: x[0])
    REPORT_DIR.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"boom_full_eval_{ts}.md"
    lines = [
        "# BOOM 全库覆盖评测（回译测试集）",
        "",
        f"- 测试条数: {n}",
        f"- 耗时: {time.time() - start:.1f}s",
        f"- token-F1: {sum_f / denom:.3f}  (P={sum_p / denom:.3f} R={sum_r / denom:.3f})",
        f"- 集合完全匹配: {exact}/{n}",
        "",
        "> 回译有噪声，绝对分偏低属正常；**重点看下面的最差 token 排行**。",
        "",
        "## 高频「缺失」token（覆盖缺口，优先补 fx_overrides）",
        "",
    ]
    for tok, cnt in missing.most_common(60):
        lines.append(f"- `{tok}` × {cnt}")
    lines += ["", "## 高频「多余」token（误译/噪声）", ""]
    for tok, cnt in spurious.most_common(40):
        lines.append(f"- `{tok}` × {cnt}")
    lines += ["", "## 最差样例", ""]
    for f, zh, en, pred in worst[:30]:
        lines.append(f"- F1={f:.2f} `{zh}` -> `{pred}`  (gold `{en}`)")
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nF1={sum_f / denom:.3f} exact={exact}/{n}\n报告: {path}")


if __name__ == "__main__":
    main()
