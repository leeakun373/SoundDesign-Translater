"""CC-CEDICT offline *weak candidate* layer (v0.1).

This module is an **offline, review-only** helper. It is NOT a runtime fallback.

Hard constraints (see ``docs/cc_cedict/cc_cedict_candidate_layer_v0_1.md``):

* It is **not** wired into ``fxengine.normalizer`` and never touches the
  Normalize default path.
* It **never** writes ``fxengine/data/canonical_tokens.csv``.
* It only produces *weak candidates* for human review / BOOM Mining.
* Promotion to a final FXName token is decided exclusively by the BOOM Mining /
  review flow, never by this tool.
* All single-character tokens are blocked by default, as is an explicit set of
  ``forbidden broad`` tokens. They can never become ``promote_candidate``.
* A candidate is only proposed for promotion when the BOOM ``target`` supports
  it (case-insensitive word-boundary match).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CEDICT_PATH = ROOT / "glossary" / "sources" / "cc-cedict" / "cedict_ts.u8"

# CC-CEDICT line format: ``繁體 简体 [pin1 yin1] /gloss 1/gloss 2/``
_LINE_RE = re.compile(r"^(\S+)\s(\S+)\s\[([^\]]*)\]\s/(.*)/\s*$")
# Parenthetical content is stripped from glosses before cleaning.
_PAREN_RE = re.compile(r"\([^)]*\)")
# Alphabetic word extraction (drops pinyin digits, punctuation, hyphens, ...).
_WORD_RE = re.compile(r"[A-Za-z]+")

#: Single characters are *always* blocked, but we also keep this explicit list of
#: known-broad tokens so the intent is documented and enforced even if the
#: single-character rule ever changes.
FORBIDDEN_BROAD_TOKENS: frozenset[str] = frozenset(
    {"打", "碰", "响", "甩", "摔", "地", "面", "开", "杯", "管", "箱"}
)

#: English words/phrases that are too generic or non-FXName to ever be a token.
#: Combined with English stop-words at the word-extraction stage.
FORBIDDEN_ENGLISH: frozenset[str] = frozenset(
    {
        "hit",
        "beat",
        "sound",
        "make",
        "noise",
        "open",
        "close",
        "thing",
        "object",
        "item",
        "place",
        "surface",
        "ground",
        "classifier",
        "measure",
        "word",
        "particle",
        "grammar",
        "surname",
        "given",
        "name",
        "old",
        "variant",
        "kangxi",
        "radical",
    }
)

#: Pure English stop-words removed during word extraction.
STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "to",
        "of",
        "for",
        "and",
        "or",
        "with",
        "by",
        "in",
        "on",
        "as",
        "at",
        "made",
        "used",
        "sb",
        "sth",
        "etc",
        "esp",
    }
)

#: Lower-cased substrings that disqualify an *entire* gloss line.
GLOSS_BLOCK_MARKERS: tuple[str, ...] = (
    "variant of",
    "old variant",
    "kangxi radical",
    "surname ",
    "given name",
    "place name",
    "measure word",
    "classifier",
    "cl:",
    "see ",
    "abbr.",
)

#: A cleaned gloss longer than this many words is considered too long.
MAX_GLOSS_WORDS = 6
#: Minimum length of an extracted candidate word (drops "of", "a", ...).
MIN_WORD_LEN = 3

_CONFIDENCE_SUPPORTED = 0.5
_CONFIDENCE_WEAK = 0.3


@dataclass
class CEDictCandidate:
    """A single weak candidate derived from a CC-CEDICT gloss."""

    raw: str
    canonical: str
    confidence: float
    reason: str
    gloss: str
    source: str = "cc_cedict"


def _title_case(word: str) -> str:
    return word[:1].upper() + word[1:].lower()


def _is_blocked_token(token: str) -> Optional[str]:
    """Return a block reason code if *token* must never promote, else ``None``."""

    stripped = token.strip()
    if len(stripped) <= 1:
        return "single_char_blocked"
    if stripped in FORBIDDEN_BROAD_TOKENS:
        return "forbidden_broad_token"
    return None


def _extract_candidate_words(gloss: str) -> List[str]:
    """Extract FXName-style candidate words from a single gloss string."""

    cleaned = _PAREN_RE.sub("", gloss).strip()
    if not cleaned:
        return []

    lower = cleaned.lower()
    if any(marker in lower for marker in GLOSS_BLOCK_MARKERS):
        return []

    words = _WORD_RE.findall(cleaned)
    if not words or len(words) > MAX_GLOSS_WORDS:
        return []

    candidates: List[str] = []
    for word in words:
        low = word.lower()
        if len(low) < MIN_WORD_LEN:
            continue
        if low in STOP_WORDS or low in FORBIDDEN_ENGLISH:
            continue
        title = _title_case(word)
        if title not in candidates:
            candidates.append(title)
    return candidates


def _target_supports(canonical: str, target: str) -> bool:
    """Case-insensitive whole-word match of *canonical* inside *target*."""

    if not target:
        return False
    pattern = r"\b" + re.escape(canonical) + r"\b"
    return re.search(pattern, target, flags=re.IGNORECASE) is not None


class CEDictIndex:
    """In-memory index from simplified Chinese token -> English glosses."""

    def __init__(self, entries: Optional[Dict[str, List[str]]] = None) -> None:
        self._entries: Dict[str, List[str]] = entries or {}

    # ------------------------------------------------------------------ build
    @classmethod
    def from_file(cls, path: Path | None = None) -> "CEDictIndex":
        """Load a CC-CEDICT ``.u8`` file. Defaults to the bundled snapshot."""

        source = Path(path) if path is not None else DEFAULT_CEDICT_PATH
        entries: Dict[str, List[str]] = {}
        with source.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.rstrip("\n")
                if not line or line.startswith("#"):
                    continue
                match = _LINE_RE.match(line)
                if not match:
                    continue
                simplified = match.group(2)
                glosses = [g for g in match.group(4).split("/") if g.strip()]
                if not glosses:
                    continue
                entries.setdefault(simplified, []).extend(glosses)
        return cls(entries)

    @classmethod
    def from_lines(cls, lines: list[str]) -> "CEDictIndex":
        """Build an index from raw CC-CEDICT text lines (handy for tests)."""

        entries: Dict[str, List[str]] = {}
        for raw_line in lines:
            line = raw_line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            match = _LINE_RE.match(line)
            if not match:
                continue
            simplified = match.group(2)
            glosses = [g for g in match.group(4).split("/") if g.strip()]
            if glosses:
                entries.setdefault(simplified, []).extend(glosses)
        return cls(entries)

    # ----------------------------------------------------------------- lookup
    def glosses(self, token: str) -> List[str]:
        return list(self._entries.get(token.strip(), []))

    def lookup(self, token: str) -> List[CEDictCandidate]:
        """Return all weak candidates for *token* (unfiltered by any target)."""

        token = token.strip()
        block_reason = _is_blocked_token(token)
        candidates: List[CEDictCandidate] = []
        seen: set[str] = set()
        for gloss in self._entries.get(token, []):
            for word in _extract_candidate_words(gloss):
                if word in seen:
                    continue
                seen.add(word)
                reason = block_reason or "weak_candidate"
                candidates.append(
                    CEDictCandidate(
                        raw=token,
                        canonical=word,
                        confidence=_CONFIDENCE_WEAK,
                        reason=reason,
                        gloss=gloss.strip(),
                    )
                )
        return candidates

    def candidates_supported_by_target(
        self, token: str, boom_target: str
    ) -> List[CEDictCandidate]:
        """Subset of :meth:`lookup` whose canonical is supported by the target."""

        if _is_blocked_token(token):
            return []
        supported: List[CEDictCandidate] = []
        for candidate in self.lookup(token):
            if _target_supports(candidate.canonical, boom_target):
                supported.append(
                    CEDictCandidate(
                        raw=candidate.raw,
                        canonical=candidate.canonical,
                        confidence=_CONFIDENCE_SUPPORTED,
                        reason="supported_by_target",
                        gloss=candidate.gloss,
                    )
                )
        return supported

    # ---------------------------------------------------------------- propose
    def propose_for_target(self, token: str, boom_target: str) -> dict:
        """Produce an offline proposal. Never writes canonical data.

        ``status`` is one of ``promote_candidate`` / ``review`` / ``blocked``.
        """

        token = token.strip()
        target = (boom_target or "").strip()
        reasons: List[str] = []

        block_reason = _is_blocked_token(token)
        if block_reason:
            reasons.append(block_reason)
            return {
                "token": token,
                "target": target,
                "status": "blocked",
                "candidates": [],
                "reasons": reasons,
            }

        weak = self.lookup(token)
        if not weak:
            reasons.append("no_cedict_entry")
            return {
                "token": token,
                "target": target,
                "status": "review",
                "candidates": [],
                "reasons": reasons,
            }

        supported = self.candidates_supported_by_target(token, target)
        if supported:
            reasons.append("target_supported")
            return {
                "token": token,
                "target": target,
                "status": "promote_candidate",
                "candidates": supported,
                "reasons": reasons,
            }

        reasons.append("no_target_support")
        return {
            "token": token,
            "target": target,
            "status": "review",
            "candidates": weak,
            "reasons": reasons,
        }
