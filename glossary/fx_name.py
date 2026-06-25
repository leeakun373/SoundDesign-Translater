"""FX name normalization and validation helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from glossary.fx_quality import find_bad_phrases


ARTICLE_RE = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-]*")
SENTENCE_VERBS = re.compile(
    r"\b(?:slipped|slides|sliding|opened|opens|pushed|pushes|pulled|pulls)\b",
    re.IGNORECASE,
)
SENTENCE_AUX = re.compile(
    r"\b(?:was|were|is|are|am|be|been|being)\b",
    re.IGNORECASE,
)
PREPOSITION_RUN = re.compile(
    r"\b(?:of|on|in|at|to|for|from|with|by)\b",
    re.IGNORECASE,
)
ZH_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
ISOLATED_DOOR_RE = re.compile(r"(?<![\u4e00-\u9fff])门(?![\u4e00-\u9fff])")
DOOR_OBJECT_TERMS = (
    "木门",
    "玻璃门",
    "铁门",
    "金属门",
    "车门",
    "前门",
    "后门",
    "滑门",
    "推拉门",
)
DOOR_EVENT_TERMS = ("开门", "关门", "关上门", "推门", "拉门", "敲门")
SINGLE_EVENT_TOKENS = {
    "heartbeat",
    "cough",
    "sneeze",
    "applause",
}
SINGLE_EVENT_SOURCES = ("心跳", "咳嗽", "打喷嚏", "喷嚏", "掌声")
MAX_NLLB_CANDIDATE_WORDS = 4


@dataclass(frozen=True)
class NllbCandidateResult:
    fragment: str | None
    reject_reason: str | None = None
    sanitized: str = ""


@dataclass(frozen=True)
class FxNameQuality:
    quality: str
    issues: list[str] = field(default_factory=list)
    required_tokens: list[str] = field(default_factory=list)
    forbidden_tokens: list[str] = field(default_factory=list)


def sanitize_fx_fragment(text: str) -> str:
    """Convert a short NLLB fallback fragment into FX-name style tokens."""
    out = text.strip().strip(" .!?;:，。！？；：")
    out = ARTICLE_RE.sub("", out)
    replacements = (
        (r"\bslipped\b|\bslid\b|\bsliding\b|\bslides\b", "Slide"),
        (r"\bpushed\s+open\b|\bpushed\b|\bpushes\b", "Push Open"),
        (r"\bpulled\s+open\b|\bpulled\b|\bpulls\b", "Pull Open"),
        (r"\bopened\b|\bopens\b", "Open"),
        (r"\bknocked\b|\bknocking\b", "Knock"),
        (r"\bmoving\b|\bmoves\b", "Move"),
    )
    for pattern, replacement in replacements:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)
    words = WORD_RE.findall(out)
    return " ".join(_title_fx_word(w) for w in words)


def accept_nllb_fx_candidate(text: str) -> NllbCandidateResult:
    """
    Sanitize and gate an NLLB fragment for FXName fallback.
    Returns empty fragment when candidate is sentence-like or unsafe.
    """
    sanitized = sanitize_fx_fragment(text)
    if not sanitized:
        return NllbCandidateResult(None, "empty", "")

    words = WORD_RE.findall(sanitized)
    if len(words) > MAX_NLLB_CANDIDATE_WORDS:
        return NllbCandidateResult(None, "too_long", sanitized)

    absolute, risk = find_bad_phrases(sanitized)
    if absolute:
        return NllbCandidateResult(None, f"bad_phrase:{absolute[0]}", sanitized)

    if risk and SENTENCE_AUX.search(sanitized):
        return NllbCandidateResult(None, f"sentence_like:{risk[0]}", sanitized)

    if _looks_like_sentence(sanitized):
        return NllbCandidateResult(None, "sentence_like", sanitized)

    if PREPOSITION_RUN.search(sanitized) and len(words) >= 3:
        return NllbCandidateResult(None, "preposition_phrase", sanitized)

    if sanitized.strip().endswith("?"):
        return NllbCandidateResult(None, "question", sanitized)

    return NllbCandidateResult(sanitized, None, sanitized)


def validate_fx_name(src_text: str, output: str) -> FxNameQuality:
    issues: list[str] = []
    required = _required_tokens(src_text)
    forbidden = _forbidden_tokens(src_text)
    words = WORD_RE.findall(output)
    out_lower = output.lower()

    if _looks_like_sentence(output):
        issues.append("sentence_like_output")
    if (len(words) <= 1 or out_lower in {"wood", "front"}) and not _is_single_event(
        src_text, words
    ):
        issues.append("low_information")

    missing = [token for token in required if token.lower() not in out_lower]
    if missing:
        issues.extend(f"missing:{token}" for token in missing)

    present_forbidden = [
        token for token in forbidden if re.search(rf"\b{re.escape(token)}\b", output, re.IGNORECASE)
    ]
    if present_forbidden:
        issues.extend(f"forbidden:{token}" for token in present_forbidden)

    return FxNameQuality(
        quality="pass" if not issues else "fail",
        issues=issues,
        required_tokens=required,
        forbidden_tokens=forbidden,
    )


def _required_tokens(src_text: str) -> list[str]:
    required: list[str] = []

    def add(token: str) -> None:
        if token not in required:
            required.append(token)

    if "金属门" in src_text:
        add("Metal")
        add("Door")
    elif "木门" in src_text:
        add("Wood")
        add("Door")
    elif "木头" in src_text or "木制" in src_text:
        add("Wood")
    if "锯木" in src_text:
        add("Saw")
        add("Wood")
    if "玻璃" in src_text:
        add("Glass")
    if "塑料" in src_text:
        add("Plastic")
    if "盒" in src_text:
        add("Box")
    if "杯子" in src_text or "入杯" in src_text:
        add("Cup")
    if "水" in src_text:
        add("Water")
    if "石头" in src_text or "石块" in src_text:
        add("Stone")
    if _requires_door(src_text):
        add("Door")
    if "倒水" in src_text:
        add("Pour")
    if "轮胎" in src_text:
        add("Tire")
    if "摩擦" in src_text:
        add("Rub")

    if "滑动" in src_text or "滑开" in src_text:
        add("Slide")
    if "推开" in src_text:
        add("Push")
        add("Open")
    if "拉开" in src_text:
        add("Pull")
        add("Open")
    if "狼嚎" in src_text:
        add("Wolf")
        add("Howl")
    elif "狼" in src_text:
        add("Wolf")
    if "火箭" in src_text:
        add("Rocket")
    if "飞过" in src_text or "飞越" in src_text:
        add("Flyby")
    if "海克斯" in src_text:
        add("Hex")
    if "宝石" in src_text:
        add("Gemstone")
    if "水晶" in src_text:
        add("Crystal")
    if "碎裂" in src_text:
        add("Shatter")
    if "破碎" in src_text:
        add("Break")
    if "流过" in src_text or "水流" in src_text:
        add("Flow")
    if "掉落" in src_text:
        add("Drop")
    if "木桌" in src_text:
        add("Wooden")
        add("Table")
    if "纸袋" in src_text:
        add("Paper")
        add("Bag")
    if "布帘" in src_text or "窗帘" in src_text:
        add("Cloth")
        add("Curtain")
    if "打碎" in src_text:
        add("Shatter")
    if "撕裂" in src_text:
        add("Tear")
    if "撞击" in src_text:
        add("Impact")
    if "怠速" in src_text:
        add("Idle")
    if "轰油门" in src_text:
        add("Rev")
    if "引擎" in src_text:
        add("Engine")
    if "停止" in src_text:
        add("Stop")
    if "拖动" in src_text or "拖拽" in src_text:
        add("Drag")
    if "打开" in src_text:
        add("Open")
    if "关闭" in src_text:
        add("Close")
    return required


def _requires_door(src_text: str) -> bool:
    if "油门" in src_text or "大门" in src_text:
        return False
    if any(term in src_text for term in DOOR_OBJECT_TERMS):
        return True
    if any(term in src_text for term in DOOR_EVENT_TERMS):
        return True
    return bool(ISOLATED_DOOR_RE.search(src_text))


def _is_single_event(src_text: str, words: list[str]) -> bool:
    if len(words) != 1:
        return False
    if words[0].lower() not in SINGLE_EVENT_TOKENS:
        return False
    return any(term in src_text for term in SINGLE_EVENT_SOURCES) or not ZH_CHAR_RE.search(
        src_text
    )


def _forbidden_tokens(src_text: str) -> list[str]:
    if "前门" in src_text:
        return []
    return ["Front"]


def _looks_like_sentence(output: str) -> bool:
    stripped = output.strip()
    if stripped.endswith((".", "?", "!")):
        return True
    if ARTICLE_RE.match(stripped):
        return True
    if SENTENCE_VERBS.search(stripped):
        return True
    if SENTENCE_AUX.search(stripped) and len(WORD_RE.findall(stripped)) >= 2:
        return True
    return False


def _title_fx_word(word: str) -> str:
    upper_words = {"FX", "SFX", "UCS"}
    if word.upper() in upper_words:
        return word.upper()
    return word[:1].upper() + word[1:].lower()
