"""FXName 探针：从文件按行读中文短句，打印译文 + 每 token 来源，标记可疑项。

用法: python tools/probe_fxname.py <inputs.txt>
可疑判定：任一 token 走 nllb / unknown / cedict（词典兜底，最易出错）。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "translator"))

from translator import api  # noqa: E402

SUSPECT = {"nllb", "cedict", "unknown"}


def main() -> None:
    path = Path(sys.argv[1])
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    n_suspect = 0
    for text in lines:
        res = api.to_fxname(text)
        parts = []
        flag = False
        for t in res.detail.traces:
            if t.kind == "ascii":
                continue
            base = (t.decision or "").split("+", 1)[0]
            if t.decision == "dropped_stop":
                continue
            tag = base
            if base in SUSPECT or not t.translated:
                tag = base.upper() if t.translated else "UNKNOWN"
                flag = True
            parts.append(f"{t.source_text}>{t.translated or '∅'}[{tag}]")
        mark = "  <== 可疑" if flag else ""
        if flag:
            n_suspect += 1
        print(f"{text}  ->  {res.text}{mark}")
        print(f"      {' '.join(parts)}")
    print(f"\n总 {len(lines)} 条，可疑 {n_suspect} 条")


if __name__ == "__main__":
    main()
