#!/usr/bin/env python3
"""UCSRenamer 接入 LocalTranslate 的两种方式示例。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def demo_direct_import(text: str) -> None:
    """同进程直接 import（适合 UCSRenamer 与翻译服务在同一 Python 环境）。"""
    from engine import NllbTranslator

    translator = NllbTranslator()
    translator.load()
    result = translator.translate(text, mode="auto", pro_mode=True)
    print("[direct import]")
    print("  input :", text)
    print("  output:", result.text)
    print("  status:", result.status_label)


def demo_http_client(text: str, base_url: str = "http://127.0.0.1:18765") -> None:
    """HTTP 调用（适合 Reaper / 其他进程 / UCSRenamer 独立运行时）。"""
    from client.python.client import LocalTranslateClient

    client = LocalTranslateClient(base_url)
    health = client.health()
    if not health.get("model_ready"):
        raise RuntimeError(
            "翻译服务模型尚未就绪，请先运行: python service/server.py"
        )
    result = client.translate(text, mode="auto", pro_mode=True)
    print("[http client]")
    print("  input :", text)
    print("  output:", result.translation)
    print("  status:", f"{result.mode} · {result.direction} · {result.ms}ms")


def main() -> None:
    sample = "ICEFric_Ice Axe Scratch Friction Ice Brick 01_ASO_Rec_CO100K"
    if len(sys.argv) > 1:
        sample = " ".join(sys.argv[1:])

    print("=== UCSRenamer integration demo ===\n")
    demo_direct_import(sample)
    print()
    try:
        demo_http_client(sample)
    except Exception as exc:
        print("[http client] skipped:", exc)
        print("提示: 另开终端运行 python service/server.py 后再试 HTTP 方式")


if __name__ == "__main__":
    main()
