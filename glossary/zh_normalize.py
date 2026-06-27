"""FXName input normalization: merge abnormal spaces inside Chinese runs."""

from __future__ import annotations

import re

ASCII_TOKEN = re.compile(
    r"(?:[A-Za-z][A-Za-z0-9+\-]*|\d+(?:\.\d+)?m)\b",
    re.IGNORECASE,
)
ZH_CHAR = re.compile(r"[\u4e00-\u9fff]")

# Punctuation that separates tokens (not merged across)
SEP_CHARS = frozenset("，。、；：！？,.!?;:")


def normalize_fxname_input(text: str) -> str:
    """
    Normalize FXName input without destroying English tokens.

    - Merge spaces between Chinese characters: 塑料 盒掉 落 → 塑料盒掉落
    - Preserve ASCII token boundaries: door 推开 wood stays separable
    - Collapse only whitespace (not all spaces — ASCII gaps remain)
    """
    if not text or not text.strip():
        return text.strip()

    parts: list[str] = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue

        word_m = ASCII_TOKEN.match(text, i)
        if word_m:
            if parts and not parts[-1].endswith(" "):
                parts.append(" ")
            parts.append(word_m.group(0))
            parts.append(" ")
            i = word_m.end()
            continue

        if ch in SEP_CHARS:
            parts.append(" ")
            i += 1
            continue

        if ZH_CHAR.match(ch):
            zh_run: list[str] = []
            while i < n:
                c = text[i]
                if ZH_CHAR.match(c):
                    zh_run.append(c)
                    i += 1
                elif c.isspace():
                    j = i + 1
                    while j < n and text[j].isspace():
                        j += 1
                    if j < n and ZH_CHAR.match(text[j]):
                        i = j
                        continue
                    break
                else:
                    break
            if zh_run:
                if parts and parts[-1] not in (" ", ""):
                    if not parts[-1].endswith(" "):
                        parts.append(" ")
                parts.append("".join(zh_run))
            continue

        parts.append(ch)
        i += 1

    merged = "".join(parts)
    return re.sub(r" +", " ", merged).strip()
