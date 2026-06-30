"""将 tools/_probe_r*.txt 固化为 pytest 回归 CSV。

输出：tests/zh_fxname_probe_regression.csv
每行记录当前后端的 expected_fxname，并标记 round/theme。
构建时若任一句出现 unknown / NLLB token 则非零退出。
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from translator import api  # noqa: E402

PROBE_GLOB = "tools/_probe_r*.txt"
OUT_CSV = ROOT / "tests" / "zh_fxname_probe_regression.csv"

ROUND_THEMES: dict[int, str] = {
    13: "工业机械",
    14: "自然动物",
    15: "科幻太空",
    16: "办公家电",
    17: "宗教武术",
    18: "交通极限",
    19: "乐器管弦",
    20: "安防应急",
    21: "极地农村",
    22: "影视舞台",
    23: "医疗康复",
    24: "学校课堂",
    25: "餐饮厨房",
    26: "动物园所",
    27: "军事战场",
    28: "机场航空",
    29: "酒店客房",
    30: "警务刑侦",
    31: "工地农村",
    32: "海运港口",
    33: "铁路列车",
    34: "汽修赛车",
    35: "广电录音",
    36: "魔法奥术",
    37: "中世纪",
    38: "赛博朋克",
    39: "幻想RPG",
    40: "恐怖游戏",
    41: "游戏UI蒸汽",
    42: "体育竞技",
    43: "法庭银行",
    44: "太空歌剧",
    45: "像素街机",
}


def _round_from_path(path: Path) -> int:
    match = re.search(r"_probe_r(\d+)\.txt$", path.name)
    if not match:
        raise ValueError(f"unexpected probe filename: {path}")
    return int(match.group(1))


def _classify_traces(traces) -> tuple[list[str], bool, bool, list[str]]:
    sources: list[str] = []
    used_nllb = False
    has_unknown = False
    unknown_tokens: list[str] = []
    for t in traces:
        if t.kind == "ascii":
            sources.append("protected")
            continue
        if t.decision == "dropped_stop":
            continue
        base = (t.decision or "").split("+", 1)[0]
        if base == "unknown" or not t.translated:
            has_unknown = True
            unknown_tokens.append(t.source_text)
            sources.append("unknown")
            continue
        sources.append(base)
        if base == "nllb":
            used_nllb = True
    return sources, used_nllb, has_unknown, unknown_tokens


def build(out_path: Path = OUT_CSV) -> int:
    rows: list[dict[str, str]] = []
    bad: list[str] = []
    seq = 0

    for path in sorted(ROOT.glob(PROBE_GLOB)):
        rnd = _round_from_path(path)
        theme = ROUND_THEMES.get(rnd, f"round{rnd}")
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            seq += 1
            rid = f"probe-{rnd:02d}-{seq:04d}"
            res = api.to_fxname(text)
            _, used_nllb, has_unknown, unknowns = _classify_traces(res.detail.traces)
            if has_unknown or used_nllb:
                bad.append(
                    f"{rid} {text!r} unknown={unknowns} nllb={used_nllb} -> {res.text!r}"
                )
            rows.append(
                {
                    "id": rid,
                    "round": str(rnd),
                    "theme": theme,
                    "input": text,
                    "expected_fxname": res.text,
                    "must_not_unknown": "yes",
                    "must_not_nllb": "yes",
                }
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "round",
                "theme",
                "input",
                "expected_fxname",
                "must_not_unknown",
                "must_not_nllb",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {len(rows)} rows -> {out_path}")
    if bad:
        print(f"BLOCKED: {len(bad)} rows with unknown/NLLB", file=sys.stderr)
        for item in bad[:20]:
            print(item, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
