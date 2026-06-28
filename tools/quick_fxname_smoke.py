"""模式1 快速冒烟工具：开发期最快反馈回路。

并排打印：输入 | NLLB原始 | 最终FXName，并展开每个 token 的译法/吸附决策/BOOM词频。
不像 FXName 时立即据此调（停用词表/吸附阈值/对齐表/fx_overrides）。

用法：
    python tools/quick_fxname_smoke.py                 # 内置代表性清单
    python tools/quick_fxname_smoke.py "喷火器" "金属门关上"   # 自定义输入
    python tools/quick_fxname_smoke.py --no-nllb-raw    # 跳过整句 NLLB 对照列（更快）
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from translator import fxname_mode  # noqa: E402

BUILTIN = [
    "喷火器",
    "遥控无人机起飞",
    "奥古斯塔 A109 飞走 01",
    "波音 747 涡轮怠速 02",
    "金属门重重关上",
    "远处雷声沉闷的轰鸣",
    "玻璃杯清脆碰撞",
    "森林里清晨的鸟鸣和微风",
    "巨大的爆炸冲击波伴随碎石",
    "脚步声在空旷走廊回响",
    "电子怪物低吼循环",
    "汽车引擎启动后加速驶过",
]


def run(inputs: list[str], show_raw: bool) -> None:
    raw_fn = None
    if show_raw:
        try:
            from translator import nllb

            raw_fn = nllb.zh2en
        except Exception:
            raw_fn = None

    for text in inputs:
        result = fxname_mode.normalize(text)
        print("=" * 78)
        print(f"输入     : {text}")
        if raw_fn is not None:
            try:
                print(f"NLLB原始 : {raw_fn(text)}")
            except Exception as exc:
                print(f"NLLB原始 : <error: {exc}>")
        print(f"最终FXName: {result.output_fxname}")
        print("  token 明细:")
        for t in result.traces:
            if t.decision == "dropped_stop":
                print(f"    - {t.source_text!r:10} [停用词，丢弃]")
                continue
            final = " ".join(t.final_words) if t.final_words else "(无)"
            print(f"    - {t.source_text!r:10} -> 译:{t.translated!r:16} "
                  f"=> {final!r:16} [{t.decision}] {t.detail}")
    print("=" * 78)


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--no-nllb-raw"]
    show_raw = "--no-nllb-raw" not in sys.argv
    inputs = args if args else BUILTIN
    run(inputs, show_raw)


if __name__ == "__main__":
    main()
