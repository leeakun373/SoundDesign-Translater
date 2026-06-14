"""音频领域中文后处理：统一 UCS 口径。"""

from __future__ import annotations

import re

TERM_FIXES: list[tuple[str, str]] = [
    (r"\bCatID\b", "CatID"),
    (r"声音效果", "音效"),
    (r"环境音", "环境声"),
    (r"环境声音", "环境声"),
    (r"\bfoley\b", "拟音"),
    (r"\bFoley\b", "拟音"),
    (r"  +", " "),
]

PUNCT_FIXES: list[tuple[str, str]] = [
    (" ,", "，"),
    (" .", "。"),
    ("..", "。"),
    (",.", "。"),
    ("，。", "。"),
    ("。。", "。"),
]


def polish_en_fx(text: str) -> str:
    """英文 FX 名：规整空格，去掉残留中文。"""
    result = re.sub(r"\s+", " ", text.strip())
    result = re.sub(r"[\u4e00-\u9fff]+", " ", result)
    result = re.sub(r"\s+", " ", result).strip()
    # 统一 Title Case（保留已有多词大写如 Room Tone）
    return " ".join(w[:1].upper() + w[1:] if w else w for w in result.split())


def polish_text(text: str, tgt_is_zh: bool) -> str:
    """按目标语言做轻量后处理。"""
    if not text or not text.strip():
        return text
    if not tgt_is_zh:
        return polish_en_fx(text)

    result = text.strip()
    for pattern, repl in TERM_FIXES:
        result = re.sub(pattern, repl, result, flags=re.IGNORECASE)
    for old, new in PUNCT_FIXES:
        result = result.replace(old, new)
    return result.strip()
