"""Order-preserving tokenizer for Chinese, English, and distance tokens."""

from __future__ import annotations

import re
from dataclasses import dataclass


DISTANCE_RE = re.compile(r"^\d+(?:\.\d+)?(?:mm|cm|m)$", re.IGNORECASE)
TOKEN_RE = re.compile(
    r"\d+(?:\.\d+)?(?:mm|cm|m)\b|[A-Za-z][A-Za-z0-9+\-]*|"
    r"\d+(?:\.\d+)?[A-Za-z]+|\d+|[\u4e00-\u9fff]+",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RawToken:
    raw: str
    kind: str
    start: int
    end: int


class FXTokenizer:
    def tokenize(self, text: str) -> list[RawToken]:
        out: list[RawToken] = []
        for match in TOKEN_RE.finditer(text):
            raw = match.group(0)
            if DISTANCE_RE.fullmatch(raw):
                kind = "distance"
            elif raw[0].isascii():
                kind = "ascii"
            else:
                kind = (
                    "zh_user"
                    if _has_explicit_space_boundary(text, match.start(), match.end())
                    else "zh"
                )
            out.append(RawToken(raw=raw, kind=kind, start=match.start(), end=match.end()))
        return out


def _has_explicit_space_boundary(text: str, start: int, end: int) -> bool:
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    return before.isspace() or after.isspace()
