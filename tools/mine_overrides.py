"""数据驱动地自动生成 fx_overrides_auto.csv（取代大部分手工调词）。

思路：对每个中文 token，候选英文 = CC-CEDICT 全部义项 ∪ canonical ∪ 对齐变体；
按 BOOM 全库词频择优。只在「某义项明显主导」时才落一条 override，避免歧义误判。

手工 translator/data/fx_overrides.csv 始终优先，作为自动结果的例外修正。

用法：
    python tools/mine_overrides.py                 # 默认阈值
    python tools/mine_overrides.py --min-freq 80 --dominance 1.5
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from glossary.fx_slots import infer_slot  # noqa: E402
from translator import align, boom_snap, cedict, overrides  # noqa: E402

OUT_PATH = ROOT / "translator" / "data" / "fx_overrides_auto.csv"


def _title(text: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in text.split())


def mine(min_freq: int, dominance: float) -> int:
    manual = set(overrides.manual_keys())
    rows: list[tuple[str, str, str, int]] = []
    start = time.time()
    tokens = cedict.headwords(min_len=1)
    for i, zh in enumerate(tokens):
        if zh in manual:
            continue
        candidates: set[str] = set(cedict.lookup_all(zh))
        candidates |= align.variants_for(zh)
        if not candidates:
            continue
        scored = sorted(((boom_snap.freq(c), c) for c in candidates), reverse=True)
        best_freq, best = scored[0]
        if best_freq < min_freq:
            continue
        if len(best.split()) > 3:  # 太长不像命名关键词
            continue
        second_freq = scored[1][0] if len(scored) > 1 else 0
        if second_freq > 0 and best_freq < dominance * second_freq:
            continue  # 歧义：无主导义项，交给 cedict/手工
        slot = infer_slot(best)
        rows.append((zh, _title(best), slot if slot != "unknown" else "", best_freq))
        if (i + 1) % 20000 == 0:
            print(f"  ...{i + 1}/{len(tokens)} ({time.time() - start:.1f}s)")

    rows.sort(key=lambda r: -r[3])
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["raw", "canonical", "slot", "boom_freq"])
        for zh, en, slot, freq in rows:
            writer.writerow([zh, en, slot, freq])
    print(f"auto overrides: {len(rows)} rows -> {OUT_PATH}  ({time.time() - start:.1f}s)")
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-freq", type=int, default=80)
    ap.add_argument("--dominance", type=float, default=1.5)
    args = ap.parse_args()
    mine(args.min_freq, args.dominance)


if __name__ == "__main__":
    main()
