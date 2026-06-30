"""批量分析探针文件，输出需修复条目。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from translator import api, overrides  # noqa: E402

SUSPECT = {"cedict", "unknown"}


def main() -> None:
    files = sys.argv[1:] or [
        "tools/_probe_r9.txt",
        "tools/_probe_r10.txt",
        "tools/_probe_r11.txt",
        "tools/_probe_r12.txt",
    ]
    issues = []
    for fname in files:
        for text in Path(fname).read_text(encoding="utf-8").splitlines():
            text = text.strip()
            if not text:
                continue
            res = api.to_fxname(text)
            bad = []
            for t in res.detail.traces:
                if t.kind != "zh":
                    continue
                base = (t.decision or "").split("+", 1)[0]
                if base in SUSPECT or not t.translated:
                    bad.append((t.source_text, t.translated or "∅", base))
            if bad:
                issues.append((text, res.text, bad))
    print(f"问题条目: {len(issues)}")
    for text, out, bad in issues:
        print("---")
        print(f"{text} -> {out}")
        for src, tr, base in bad:
            ov = overrides.lookup(src)
            ovc = ov["canonical"] if ov else None
            print(f"  {src} => {tr} [{base}] ov={ovc}")


if __name__ == "__main__":
    main()
