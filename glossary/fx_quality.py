"""FXName quality evaluation: bad-phrase gate and heuristic labels."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

WORD_RE = re.compile(
    r"\d+(?:\.\d+)?(?:mm|cm|m)\b|[A-Za-z][A-Za-z0-9+\-]*",
    re.IGNORECASE,
)
ZH_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
ARTICLE_RE = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)

# Absolute forbidden phrases — any match => fail
ABSOLUTE_BAD_PHRASES: tuple[str, ...] = (
    "it s",
    "it's",
    "i m",
    "i'm",
    "you",
    "your",
    "get out of here",
    "oh my god",
    "how can i help you",
    "what are you doing",
    "was knocked",
    "were",
    "there is",
    "this is",
    "that is",
    "i am",
    "you are",
    "he is",
    "she is",
    "they are",
    "on my way",
    "sound effect",
    "make it boom style",
)

# Sentence-like risk phrases — contribute to fail / needs_review
RISK_BAD_PHRASES: tuple[str, ...] = (
    "the sound of",
    "it is",
    "there is",
    "going to",
    "come on",
)

# Standalone risk auxiliaries (whole-word)
RISK_AUX_WORDS: frozenset[str] = frozenset({"was", "were", "is", "are", "am"})

PRONOUN_WORDS: frozenset[str] = frozenset({"i", "you", "he", "she", "they"})

SENTENCE_VERB_AFTER_AUX = re.compile(
    r"\b(?:was|were|is|are|am)\s+(?:knocked|going|coming|doing|helping|moving|over|down|up)\b",
    re.IGNORECASE,
)
SENTENCE_VERBS = re.compile(
    r"\b(?:slipped|slides|sliding|opened|opens|pushed|pushes|pulled|pulls)\b",
    re.IGNORECASE,
)


CANONICAL_FX_ISSUES: frozenset[str] = frozenset(
    {
        "bad_phrase",
        "sentence_like_output",
        "unknown_zh",
        "mixed_language_residue",
        "empty_output",
        "too_long",
        "over_expanded",
        "spacing_suspect",
        "duplicate_token",
        "nllb_candidate_rejected",
        "unsafe_fragment_rejected",
    }
)

ISSUE_ALIASES: dict[str, str] = {
    "natural_sentence": "sentence_like_output",
    "sentence_like": "sentence_like_output",
    "nllb_rejected": "nllb_candidate_rejected",
}

STRUCTURAL_ONLY_ISSUES: frozenset[str] = frozenset({"low_information"})


def normalize_fx_issue(issue: str) -> str | None:
    """Map legacy/structural issue labels to the canonical FXName issue set."""
    if issue.startswith("rejected_nllb_candidate:"):
        return "nllb_candidate_rejected"
    if issue in ISSUE_ALIASES:
        return ISSUE_ALIASES[issue]
    if issue in STRUCTURAL_ONLY_ISSUES or issue.startswith(("missing:", "forbidden:")):
        return None
    if issue in CANONICAL_FX_ISSUES:
        return issue
    return issue


def normalize_fx_issues(issues: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for issue in issues:
        canon = normalize_fx_issue(issue)
        if canon and canon not in seen:
            seen.add(canon)
            normalized.append(canon)
    return normalized


@dataclass(frozen=True)
class FxQualityResult:
    quality: str  # pass | needs_review | fail
    issues: list[str] = field(default_factory=list)
    matched_bad_phrases: list[str] = field(default_factory=list)
    output_token_count: int = 0


def _normalize_for_phrase_match(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def find_bad_phrases(output: str) -> tuple[list[str], list[str]]:
    """Return (absolute_matches, risk_matches)."""
    normalized = _normalize_for_phrase_match(output)
    words_lower = [w.lower() for w in WORD_RE.findall(output)]

    absolute: list[str] = []
    for phrase in ABSOLUTE_BAD_PHRASES:
        if " " in phrase:
            if phrase in normalized:
                absolute.append(phrase)
        elif phrase in words_lower:
            absolute.append(phrase)

    risk: list[str] = []
    for phrase in RISK_BAD_PHRASES:
        if phrase in normalized:
            risk.append(phrase)
    for word in RISK_AUX_WORDS:
        if word in words_lower and word not in absolute:
            risk.append(word)

    return absolute, risk


def _has_duplicate_tokens(words: list[str]) -> bool:
    if len(words) < 2:
        return False
    lower = [w.lower() for w in words]
    for i in range(len(lower) - 1):
        if lower[i] == lower[i + 1]:
            return True
    counts: dict[str, int] = {}
    for w in lower:
        counts[w] = counts.get(w, 0) + 1
    return any(c >= 2 and w in {"door", "knock", "open", "close", "hit", "break"} for w, c in counts.items())


def _looks_sentence_like(output: str) -> bool:
    stripped = output.strip()
    if stripped.endswith((".", "?", "!")):
        return True
    if ARTICLE_RE.match(stripped):
        return True
    if SENTENCE_VERBS.search(stripped):
        return True
    if SENTENCE_VERB_AFTER_AUX.search(stripped):
        return True
    return False


def evaluate_fx_output(
    input_text: str,
    output: str,
    *,
    debug: dict | None = None,
    input_is_spacing_fuzz: bool = False,
) -> FxQualityResult:
    """Evaluate FXName translation output quality."""
    issues: list[str] = []
    matched_bad: list[str] = []
    debug = debug or {}

    words = WORD_RE.findall(output)
    token_count = len(words)
    out_stripped = output.strip()

    if input_text.strip() and not out_stripped:
        issues.append("empty_output")

    absolute, risk = find_bad_phrases(output)
    if absolute:
        issues.append("bad_phrase")
        matched_bad.extend(absolute)

    pronouns = [w for w in words if w.lower() in PRONOUN_WORDS]
    if pronouns:
        issues.append("bad_phrase")
        for p in pronouns:
            label = p.lower()
            if label not in matched_bad:
                matched_bad.append(label)

    if risk and "bad_phrase" not in issues:
        issues.append("sentence_like_output")
        matched_bad.extend(r for r in risk if r not in matched_bad)

    if _looks_sentence_like(output):
        if "sentence_like_output" not in issues:
            issues.append("sentence_like_output")

    if token_count > 8:
        issues.append("too_long")
        if "over_expanded" not in issues:
            issues.append("over_expanded")

    if ZH_CHAR_RE.search(output):
        issues.append("mixed_language_residue")

    unknown_zh = debug.get("unknown_zh") or []
    if unknown_zh:
        issues.append("unknown_zh")

    if input_is_spacing_fuzz:
        issues.append("spacing_suspect")

    if _has_duplicate_tokens(words):
        issues.append("duplicate_token")

    if debug.get("hybrid_fallback") and debug.get("candidate_fragments"):
        frags = debug.get("candidate_fragments") or []
        for frag in frags:
            abs_hits, _ = find_bad_phrases(str(frag))
            if abs_hits:
                issues.append("nllb_candidate_rejected")
                break

    # Deduplicate issues preserving order
    seen: set[str] = set()
    deduped_issues: list[str] = []
    for issue in issues:
        if issue not in seen:
            seen.add(issue)
            deduped_issues.append(issue)
    issues = deduped_issues

    if "bad_phrase" in issues or "empty_output" in issues:
        quality = "fail"
    elif issues:
        quality = "needs_review"
    else:
        quality = "pass"

    return FxQualityResult(
        quality=quality,
        issues=issues,
        matched_bad_phrases=matched_bad,
        output_token_count=token_count,
    )
