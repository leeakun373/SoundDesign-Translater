"""模式1 自验收：用 BOOM ONE 1000 对中英 FXName 衡量 token 级 P/R/F1 与近似完全匹配。

对比 baseline = 旧确定性流水线在同一语料上的 output_fxname 列。

用法：
    python tools/eval_translator.py            # 全量 1000 对
    python tools/eval_translator.py --limit 100
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from translator import fxname_mode  # noqa: E402

SAMPLES = ROOT / "docs" / "boom_mining" / "boom_one_mining_v0_1_b001_samples.csv"
REPORT_DIR = ROOT / "reports"

_TOK_RE = re.compile(r"[a-z0-9][a-z0-9+\-]*")


def tokenize(text: str) -> list[str]:
    return _TOK_RE.findall((text or "").lower())


def prf(pred: list[str], gold: list[str]) -> tuple[float, float, float]:
    if not pred and not gold:
        return 1.0, 1.0, 1.0
    pset, gset = set(pred), set(gold)
    if not pset:
        return 0.0, 0.0, 0.0
    if not gset:
        return 0.0, 0.0, 0.0
    inter = len(pset & gset)
    p = inter / len(pset)
    r = inter / len(gset)
    f = 0.0 if (p + r) == 0 else 2 * p * r / (p + r)
    return p, r, f


def evaluate(limit: int | None) -> dict:
    rows = []
    with SAMPLES.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(row)
    if limit:
        rows = rows[:limit]

    n = len(rows)
    sum_p = sum_r = sum_f = 0.0
    base_p = base_r = base_f = 0.0
    exact = base_exact = 0
    full_f1 = 0
    worst: list[tuple[float, str, str, str]] = []
    best_examples: list[tuple[str, str, str]] = []

    start = time.time()
    for i, row in enumerate(rows):
        zh = row.get("zh_fxname", "")
        gold = tokenize(row.get("en_fxname", ""))
        pred_text = fxname_mode.normalize(zh).output_fxname
        pred = tokenize(pred_text)
        base = tokenize(row.get("output_fxname", ""))

        p, r, f = prf(pred, gold)
        sum_p += p; sum_r += r; sum_f += f
        if set(pred) == set(gold):
            exact += 1
        if f == 1.0:
            full_f1 += 1

        bp, br, bf = prf(base, gold)
        base_p += bp; base_r += br; base_f += bf
        if set(base) == set(gold) and gold:
            base_exact += 1

        worst.append((f, zh, row.get("en_fxname", ""), pred_text))
        if (i + 1) % 200 == 0:
            print(f"  ...{i + 1}/{n} ({time.time() - start:.1f}s)")

    worst.sort(key=lambda x: x[0])
    return {
        "n": n,
        "elapsed": time.time() - start,
        "p": sum_p / n, "r": sum_r / n, "f": sum_f / n,
        "exact": exact, "full_f1": full_f1,
        "base_p": base_p / n, "base_r": base_r / n, "base_f": base_f / n,
        "base_exact": base_exact,
        "worst": worst[:25],
        "best": [w for w in reversed(worst) if w[0] >= 0.99][:25],
    }


def write_report(res: dict) -> Path:
    REPORT_DIR.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"translator_eval_{ts}.md"
    lines = [
        "# Translator 模式1 自验收报告",
        "",
        f"- 样本: BOOM ONE 中英 FXName {res['n']} 对",
        f"- 耗时: {res['elapsed']:.1f}s",
        "",
        "## 指标对比（token 级，集合口径）",
        "",
        "| 指标 | 新混合引擎 | 旧确定性流水线(baseline) |",
        "|------|-----------|--------------------------|",
        f"| Precision | {res['p']:.3f} | {res['base_p']:.3f} |",
        f"| Recall | {res['r']:.3f} | {res['base_r']:.3f} |",
        f"| F1 | {res['f']:.3f} | {res['base_f']:.3f} |",
        f"| 集合完全匹配 | {res['exact']}/{res['n']} | {res['base_exact']}/{res['n']} |",
        f"| F1==1.0 条数 | {res['full_f1']}/{res['n']} | - |",
        "",
        "## 完全匹配样例（新引擎）",
        "",
    ]
    for f, zh, gold, pred in res["best"][:15]:
        lines.append(f"- `{zh}` -> `{pred}`  (gold `{gold}`)")
    lines += ["", "## 最差样例（待迭代）", ""]
    for f, zh, gold, pred in res["worst"][:20]:
        lines.append(f"- F1={f:.2f} `{zh}` -> `{pred}`  (gold `{gold}`)")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    print(f"评测中（limit={args.limit or 'all'}）...")
    res = evaluate(args.limit)
    print(f"\n新引擎  P={res['p']:.3f} R={res['r']:.3f} F1={res['f']:.3f} "
          f"exact={res['exact']}/{res['n']} fullF1={res['full_f1']}")
    print(f"baseline P={res['base_p']:.3f} R={res['base_r']:.3f} F1={res['base_f']:.3f} "
          f"exact={res['base_exact']}/{res['n']}")
    path = write_report(res)
    print(f"报告: {path}")


if __name__ == "__main__":
    main()
