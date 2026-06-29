"""从「精翻」双语对照里挖 zh->en token 覆盖（观测真值，远比 cedict×词频靠谱）。

输入：docs/训练数据/*.csv（表头 完整原始名字,原FXName,中文翻译）
输出：
  translator/data/fx_overrides_bilingual.csv   挖到的高置信覆盖
  translator/data/jingfan_holdout.csv          留出集（不参与挖词，供诚实评测）

对齐策略：
  - jieba 切中文、按词切英文；
  - 若两侧 token 数相同 → 位置对齐加权（强信号）；
  - 否则用「同句共现」累计（弱信号）；
  - 每个中文 token 取得票最高的英文，要求 支持度>=MIN_SUPPORT 且 占比>=DOMINANCE。

用法：
  python tools/mine_overrides_bilingual.py            # 80/20 留出
  python tools/mine_overrides_bilingual.py --all      # 全部用于挖词（不留出）
"""

from __future__ import annotations

import argparse
import csv
import glob
import re
import sys
import zlib
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from translator import overrides  # noqa: E402
from translator import segment as seg  # noqa: E402
from translator.fxname_mode import EN_DROP, ZH_STOP, _title  # noqa: E402

DATA_DIR = ROOT / "docs" / "训练数据"
OUT_PATH = ROOT / "translator" / "data" / "fx_overrides_bilingual.csv"
HOLDOUT_PATH = ROOT / "translator" / "data" / "jingfan_holdout.csv"

MIN_SUPPORT = 4      # 该中文 token 至少出现这么多行
MIN_BEST = 4         # 最佳英文「共现行数」下限（要有实证）
DICE_MIN = 0.06      # 最佳英文的 Dice 关联度下限
RATIO = 1.25         # 最佳 / 次佳 关联度之比（要明显胜出）
POS_BONUS = 3        # 位置对齐(等长)给的额外共现票，强信号

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z+\-]*")
_NUM_RE = re.compile(r"^\d+[a-z]?$", re.I)


def en_tokens(text: str) -> list[str]:
    out = []
    for w in _WORD_RE.findall(text or ""):
        lw = w.lower()
        if lw in EN_DROP or _NUM_RE.match(lw):
            continue
        out.append(lw)
    return out


def zh_tokens(text: str) -> list[str]:
    out = []
    for s in seg.segment(text):
        if s.kind != "zh":
            continue
        w = s.text
        if len(w) == 1 and w in ZH_STOP:
            continue
        out.append(w)
    return out


def is_holdout(zh: str, frac: float) -> bool:
    if frac <= 0:
        return False
    bucket = zlib.crc32(zh.encode("utf-8")) % 100
    return bucket < int(frac * 100)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="不留出，全部用于挖词")
    ap.add_argument("--holdout-frac", type=float, default=0.2)
    args = ap.parse_args()
    frac = 0.0 if args.all else args.holdout_frac

    pairs: list[tuple[str, str]] = []
    seen: dict[str, str] = {}
    for f in glob.glob(str(DATA_DIR / "**" / "*.csv"), recursive=True):
        base = Path(f).name
        if base not in seen or "精确翻译" in f:
            seen[base] = f
    for f in seen.values():
        with open(f, encoding="utf-8-sig", newline="") as h:
            reader = csv.DictReader(h)
            if "原FXName" not in (reader.fieldnames or []):
                continue
            for row in reader:
                gold = (row.get("原FXName") or "").strip()
                zh = (row.get("中文翻译") or "").strip()
                if gold and zh:
                    pairs.append((zh, gold))

    if not pairs:
        print("未找到精翻数据"); sys.exit(1)

    manual = overrides.manual_keys()
    cooc: dict[str, Counter] = defaultdict(Counter)   # 行级共现(含位置加权)
    raw_cooc: dict[str, Counter] = defaultdict(Counter)  # 纯行级共现(算实证用)
    zfreq: Counter = Counter()   # 中文 token 出现的行数
    efreq: Counter = Counter()   # 英文 token 出现的行数
    holdout_rows: list[tuple[str, str]] = []
    n_train = 0

    for zh, en in pairs:
        if is_holdout(zh, frac):
            holdout_rows.append((zh, en))
            continue
        n_train += 1
        zts, ets = zh_tokens(zh), en_tokens(en)
        if not zts or not ets:
            continue
        zset, eset = set(zts), set(ets)
        for zt in zset:
            zfreq[zt] += 1
            for et in eset:
                cooc[zt][et] += 1
                raw_cooc[zt][et] += 1
        for et in eset:
            efreq[et] += 1
        if len(zts) == len(ets):  # 等长：位置对齐是强信号
            for zt, et in zip(zts, ets):
                cooc[zt][et] += POS_BONUS

    mined: list[tuple[str, str, float]] = []
    for zt, counter in cooc.items():
        if zfreq[zt] < MIN_SUPPORT or zt in manual:
            continue
        # Dice 关联度：2*共现 /(中文行数+英文行数)，降权到处都出现的常见英文词
        scored = sorted(
            ((et, raw_cooc[zt][et], (2.0 * cnt) / (zfreq[zt] + efreq[et]))
             for et, cnt in counter.items()),
            key=lambda x: -x[2],
        )
        best_en, best_raw, best_s = scored[0]
        if best_raw < MIN_BEST or best_s < DICE_MIN:
            continue
        second_s = scored[1][2] if len(scored) > 1 else 0.0
        if second_s > 0 and best_s / second_s < RATIO:
            continue
        mined.append((zt, _title(best_en), round(best_s, 3)))

    mined.sort(key=lambda x: -x[2])
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8", newline="") as h:
        w = csv.writer(h)
        w.writerow(["raw", "canonical", "slot", "support"])
        for raw, canon, sup in mined:
            w.writerow([raw, canon, "", sup])

    if holdout_rows:
        with HOLDOUT_PATH.open("w", encoding="utf-8", newline="") as h:
            w = csv.writer(h)
            w.writerow(["完整原始名字", "原FXName", "中文翻译"])
            for zh, en in holdout_rows:
                w.writerow(["", en, zh])

    print(f"训练对: {n_train}  挖出覆盖: {len(mined)}  留出: {len(holdout_rows)}")
    print(f"-> {OUT_PATH}")
    if holdout_rows:
        print(f"-> {HOLDOUT_PATH}")
    print("\nTop 30 挖出映射:")
    for raw, canon, sup in mined[:30]:
        print(f"  {raw} -> {canon}  ({sup})")


if __name__ == "__main__":
    main()
