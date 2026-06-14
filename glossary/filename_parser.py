"""音效库文件名拆段与格式 B 翻译。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from glossary.matcher import GlossaryMatcher

DEVICE_CODE_RE = re.compile(r"^[A-Z]{1,4}\d+[A-Z0-9]*$", re.IGNORECASE)
FILENAME_RESERVED = frozenset({
    "rec", "raw", "mono", "stereo", "l", "r", "lm", "rm",
    "hi", "lo", "mid", "firing", "pounder",
})
AUDIO_EXTS = frozenset({".wav", ".mp3", ".flac", ".aif", ".aiff", ".ogg", ".m4a", ".wma"})


def _split_audio_ext(token: str) -> tuple[str, str]:
    """ASO.wav → (ASO, .wav)，避免扩展名导致 never_translate 失效。"""
    lower = token.lower()
    for ext in AUDIO_EXTS:
        if lower.endswith(ext):
            return token[: -len(ext)], token[-len(ext) :]
    return token, ""


def _token_core(token: str) -> str:
    core, _ = _split_audio_ext(token)
    return core


class SegmentKind(str, Enum):
    CATID = "catid"
    CODE = "code"
    TERM = "term"


@dataclass
class Segment:
    text: str
    kind: SegmentKind = SegmentKind.TERM
    sep_after: str = ""


@dataclass
class FilenameChunk:
    segments: list[Segment] = field(default_factory=list)
    sep_after: str = ""


def _is_code_token(token: str, matcher: GlossaryMatcher) -> bool:
    core = _token_core(token.strip())
    t = core.strip()
    if not t:
        return True
    if t.isdigit():
        return True
    if t.lower() in FILENAME_RESERVED:
        return True
    if DEVICE_CODE_RE.match(t):
        return True
    if matcher.is_never_translate(t):
        return True
    entry = matcher.lookup_en(t)
    if entry and entry.action == "never_translate":
        return True
    return False


def _classify_token(token: str, matcher: GlossaryMatcher) -> SegmentKind:
    core = _token_core(token)
    if matcher.is_catid(core):
        return SegmentKind.CATID
    if _is_code_token(token, matcher):
        return SegmentKind.CODE
    return SegmentKind.TERM


def parse_filename(text: str, matcher: GlossaryMatcher) -> list[FilenameChunk]:
    chunks: list[FilenameChunk] = []
    parts = text.split("_")
    for i, part in enumerate(parts):
        chunk = FilenameChunk()
        if i < len(parts) - 1:
            chunk.sep_after = "_"
        if not part:
            chunks.append(chunk)
            continue
        if matcher.is_catid(part.strip()):
            chunk.segments.append(Segment(part, SegmentKind.CATID))
            chunks.append(chunk)
            continue
        tokens = part.split(" ")
        for j, token in enumerate(tokens):
            core, ext = _split_audio_ext(token)
            seg = Segment(
                text=token,
                kind=_classify_token(token, matcher),
                sep_after=" " if j < len(tokens) - 1 else "",
            )
            chunk.segments.append(seg)
        chunks.append(chunk)
    return chunks


def _lookup_phrase(matcher: GlossaryMatcher, phrase: str, to_zh: bool) -> str | None:
    entry = matcher.lookup_en(phrase)
    if entry and entry.action == "translate" and entry.zh:
        return entry.zh if to_zh else entry.en
    return matcher.translate_token(phrase, to_zh=to_zh)


def _translate_token_list(
    tokens: list[str],
    matcher: GlossaryMatcher,
    nllb_fn: Callable[[str], str],
    to_zh: bool,
) -> tuple[list[str], int]:
    """支持多词短语优先（如 Ice Axe）。"""
    out: list[str] = []
    hits = 0
    i = 0
    while i < len(tokens):
        token = tokens[i]
        core, ext = _split_audio_ext(token)
        if _is_code_token(token, matcher):
            out.append(token)
            i += 1
            continue

        matched = False
        for n in (4, 3, 2, 1):
            if i + n > len(tokens):
                continue
            phrase_parts = tokens[i : i + n]
            phrase = " ".join(_token_core(t) for t in phrase_parts)
            mapped = _lookup_phrase(matcher, phrase, to_zh)
            if mapped:
                # 保留末 token 上的音频扩展名
                last_ext = _split_audio_ext(phrase_parts[-1])[1]
                out.append(mapped + last_ext)
                hits += 1
                i += n
                matched = True
                break
        if not matched:
            translated = nllb_fn(core)
            out.append(translated + ext)
            i += 1
    return out, hits


def chunks_to_string(chunks: list[FilenameChunk]) -> str:
    parts: list[str] = []
    for ci, chunk in enumerate(chunks):
        seg_parts: list[str] = []
        for seg in chunk.segments:
            seg_parts.append(seg.text)
            if seg.sep_after:
                seg_parts.append(seg.sep_after)
        parts.append("".join(seg_parts))
        if chunk.sep_after and ci < len(chunks) - 1:
            parts.append(chunk.sep_after)
    return "".join(parts)


def translate_filename(
    text: str,
    matcher: GlossaryMatcher,
    nllb_fn: Callable[[str], str],
    to_zh: bool,
) -> tuple[str, int]:
    chunks = parse_filename(text, matcher)
    total_hits = 0

    for chunk in chunks:
        if len(chunk.segments) == 1 and chunk.segments[0].kind == SegmentKind.CATID:
            continue

        tokens = [seg.text for seg in chunk.segments if seg.text]
        if not tokens:
            continue

        if all(_is_code_token(t, matcher) or matcher.is_catid(t) for t in tokens):
            continue

        new_tokens, hits = _translate_token_list(tokens, matcher, nllb_fn, to_zh)
        total_hits += hits

        chunk.segments = [
            Segment(
                text=new_tokens[i],
                kind=_classify_token(new_tokens[i], matcher),
                sep_after=" " if i < len(new_tokens) - 1 else "",
            )
            for i in range(len(new_tokens))
        ]

    return chunks_to_string(chunks), total_hits


def looks_like_filename(text: str, matcher: GlossaryMatcher) -> bool:
    if "_" not in text:
        return False
    tokens = re.split(r"[_\s]+", text.strip())
    catid_hits = sum(1 for t in tokens if t and matcher.is_catid(t))
    code_hits = sum(1 for t in tokens if t and matcher.is_never_translate(t))
    return catid_hits >= 1 or (text.count("_") >= 2 and code_hits >= 1)
