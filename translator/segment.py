"""中文分词：jieba + 自定义词典，并保护 ASCII / 数字 / 型号码原样保留。

修复「喷火器」被逐字拆开的问题：自定义词典来自 CC-CEDICT 词头 ∪ canonical zh raw，
保证常见整词不被切碎。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import jieba

from translator import cedict, overrides

USERDICT_PATH = Path(__file__).resolve().parent / "data" / "jieba_userdict.txt"

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]+")


@dataclass(frozen=True)
class Segment:
    text: str
    kind: str  # "zh" | "ascii"


def build_userdict(path: Path = USERDICT_PATH) -> int:
    """生成 jieba 自定义词典文件，返回写入词条数。"""
    words: set[str] = set()
    for word in cedict.headwords(min_len=2):
        words.add(word)
    for word in overrides.keys():
        if len(word) >= 2 and _CJK_RE.fullmatch(word):
            words.add(word)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for word in sorted(words):
            # jieba 词典格式：词 [词频] [词性]；给 canonical/术语适当高频
            handle.write(f"{word} 100\n")
    return len(words)


@lru_cache(maxsize=1)
def _tokenizer() -> jieba.Tokenizer:
    tok = jieba.Tokenizer()
    tok.initialize()
    if not USERDICT_PATH.exists():
        build_userdict()
    tok.load_userdict(str(USERDICT_PATH))
    return tok


def _split_runs(text: str) -> list[Segment]:
    """按 CJK / 非 CJK 切成连续块，保留顺序。"""
    runs: list[Segment] = []
    pos = 0
    for match in _CJK_RE.finditer(text):
        if match.start() > pos:
            chunk = text[pos:match.start()]
            if chunk.strip():
                runs.append(Segment(chunk.strip(), "ascii"))
        runs.append(Segment(match.group(0), "zh"))
        pos = match.end()
    if pos < len(text):
        chunk = text[pos:]
        if chunk.strip():
            runs.append(Segment(chunk.strip(), "ascii"))
    return runs


def segment(text: str) -> list[Segment]:
    """返回有序 token 列表。zh 块经 jieba 切词，ascii 块按空白再拆。"""
    out: list[Segment] = []
    for run in _split_runs(text):
        if run.kind == "ascii":
            for piece in run.text.split():
                out.append(Segment(piece, "ascii"))
            continue
        for word in _tokenizer().lcut(run.text):
            word = word.strip()
            if word:
                out.append(Segment(word, "zh"))
    return out


if __name__ == "__main__":
    import sys

    if "--build" in sys.argv:
        count = build_userdict()
        print(f"userdict written: {count} words -> {USERDICT_PATH}")
    samples = [
        "喷火器",
        "遥控无人机",
        "奥古斯塔 A109 飞走 01",
        "金属门重重关上",
        "远处雷声沉闷的轰鸣",
    ]
    for s in samples:
        print(s, "=>", [seg.text for seg in segment(s)])
