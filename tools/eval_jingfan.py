"""用「精翻」CSV 评测当前管线（真实人/AI 翻译的中英对照，比回译干净得多）。

精翻 CSV 格式（docs/训练数据/*.csv，表头）：
    完整原始名字, 原FXName, 中文翻译
我们喂「中文翻译」给模式1，与「原FXName」(gold) 对比。

用法：
    python tools/eval_jingfan.py
    python tools/eval_jingfan.py --holdout translator/data/jingfan_holdout.csv  # 只评held-out
"""

from __future__ import annotations

import argparse
import csv
import glob
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from translator import fxname_mode  # noqa: E402

DATA_DIR = ROOT / "docs" / "训练数据"
REPORT_DIR = ROOT / "reports"

_TOK_RE = re.compile(r"[a-z0-9][a-z0-9+\-]*")
_NUM_RE = re.compile(r"^\d+[a-z]?$")


def tokenize(text: str) -> list[str]:
    return [t for t in _TOK_RE.findall((text or "").lower()) if not _NUM_RE.match(t)]


def load_pairs(holdout: str | None) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    if holdout:
        files = [Path(holdout)]
    else:
        files = [Path(f) for f in glob.glob(str(DATA_DIR / "*.csv"))]
    for path in files:
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if "原FXName" not in (reader.fieldnames or []):
                continue
            for row in reader:
                gold = (row.get("原FXName") or "").strip()
                zh = (row.get("中文翻译") or "").strip()
                if gold and zh:
                    pairs.append((zh, gold))
    return pairs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    pairs = load_pairs(args.holdout)
    if args.limit:
        pairs = pairs[: args.limit]
    if not pairs:
        print("未找到精翻数据（docs/训练数据/*.csv 含表头 完整原始名字,原FXName,中文翻译）")
        sys.exit(1)

    n = len(pairs)
    sum_p = sum_r = sum_f = 0.0
    exact = 0
    missing = Counter()
    worst: list[tuple[float, str, str, str]] = []
    start = time.time()

    for i, (zh, gold_text) in enumerate(pairs):
        gold = tokenize(gold_text)
        pred_text = fxname_mode.normalize(zh).output_fxname
        pred = tokenize(pred_text)
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
        worst.append((f, zh, gold_text, pred_text))
        if (i + 1) % 200 == 0:
            print(f"  ...{i + 1}/{n} ({time.time() - start:.1f}s)")

    worst.sort(key=lambda x: x[0])
    REPORT_DIR.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"jingfan_eval_{ts}.md"
    lines = [
        "# 精翻评测（真实中英对照）",
        "",
        f"- 条数: {n}（{'held-out' if args.holdout else '全部精翻'}）",
        f"- token-F1: {sum_f / n:.3f}  (P={sum_p / n:.3f} R={sum_r / n:.3f})",
        f"- 集合完全匹配: {exact}/{n}",
        "",
        "## 高频「缺失」token（最该补的词）",
        "",
    ]
    for tok, cnt in missing.most_common(50):
        lines.append(f"- `{tok}` × {cnt}")
    lines += ["", "## 最差样例", ""]
    for f, zh, gold, pred in worst[:30]:
        lines.append(f"- F1={f:.2f} `{zh}` -> `{pred}`  (gold `{gold}`)")
    lines += ["", "## 完全匹配样例", ""]
    for f, zh, gold, pred in [w for w in reversed(worst) if w[0] >= 0.999][:20]:
        lines.append(f"- `{zh}` -> `{pred}`")
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nF1={sum_f / n:.3f} exact={exact}/{n}\n报告: {path}")


if __name__ == "__main__":
    main()
