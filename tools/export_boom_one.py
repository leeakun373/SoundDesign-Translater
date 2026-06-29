"""把纯英版 BOOM ONE 目录导出成可填的精翻模板（折叠编号变体省 token）。

输入： docs/训练数据/BOOM ONE 英文音效目录.xlsx（列含 Filename, FXName）
输出： docs/训练数据/精确翻译/BOOM_ONE_NN.csv  （三列，中文翻译留空）

折叠：把结尾的变体编号去掉再去重，例如
  Augusta A109 Fly Interior Steady Sequence 01/02/03  -> 视为同一条
这样词汇全保留、体量大降，AI 翻一遍即可学到 BOOM ONE 全部受控词汇。

用法：
  python tools/export_boom_one.py                 # 折叠去重 + 每批800行
  python tools/export_boom_one.py --chunk 1000     # 自定每批大小
  python tools/export_boom_one.py --no-dedup       # 保留全部4万条
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "训练数据" / "BOOM ONE 英文音效目录.xlsx"
OUT_DIR = ROOT / "docs" / "训练数据" / "精确翻译"

_TAIL_NUM = re.compile(r"\s+\d{1,3}$")  # 去掉结尾的变体编号(01/02/...)，保留A109这种中段型号码


def collapse_key(fxname: str) -> str:
    return _TAIL_NUM.sub("", fxname).strip().lower()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk", type=int, default=800)
    ap.add_argument("--no-dedup", action="store_true")
    args = ap.parse_args()

    wb = openpyxl.load_workbook(str(SRC), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    header = list(next(rows))
    fi = header.index("Filename")
    ni = header.index("FXName")

    seen: set[str] = set()
    out_rows: list[tuple[str, str]] = []
    total = 0
    for r in rows:
        total += 1
        filename = (r[fi] or "").strip()
        fxname = (r[ni] or "").strip()
        if not fxname:
            continue
        if not args.no_dedup:
            key = collapse_key(fxname)
            if key in seen:
                continue
            seen.add(key)
        out_rows.append((filename, fxname))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    n_files = 0
    for start in range(0, len(out_rows), args.chunk):
        n_files += 1
        chunk = out_rows[start:start + args.chunk]
        path = OUT_DIR / f"BOOM_ONE_{n_files:02d}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as h:
            w = csv.writer(h)
            w.writerow(["完整原始名字", "原FXName", "中文翻译"])
            for filename, fxname in chunk:
                w.writerow([filename, fxname, ""])

    print(f"原始 {total} 条 -> 折叠后 {len(out_rows)} 条唯一 FXName")
    print(f"切成 {n_files} 个批次文件（每批 {args.chunk}）-> {OUT_DIR}")
    print("文件名： BOOM_ONE_01.csv ... BOOM_ONE_{:02d}.csv".format(n_files))


if __name__ == "__main__":
    main()
