"""Slot-aware assembly for short English FX names."""

from __future__ import annotations

import re
from dataclasses import dataclass

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-]*")
SLOT_ORDER = (
    "modifier",
    "design",
    "material",
    "object",
    "source",
    "creature_sound",
    "action",
    "motion",
    "acoustic",
    "detail",
    "unknown",
)
TOKEN_SLOT_OVERRIDES = {
    "box": "object",
    "cup": "object",
    "door": "object",
    "drawer": "object",
    "floor": "object",
    "table": "object",
    "bag": "object",
    "curtain": "object",
    "rocket": "object",
    "rock": "object",
    "stone": "object",
    "engine": "source",
    "car": "source",
    "wood": "material",
    "wooden": "material",
    "plastic": "material",
    "glass": "material",
    "metal": "material",
    "cloth": "material",
    "paper": "material",
    "water": "material",
    "fire": "material",
    "ice": "material",
    "leather": "material",
    "flow": "action",
    "over": "detail",
    "flyby": "motion",
    "whoosh": "motion",
    "driveby": "motion",
    "swish": "motion",
    "drop": "action",
    "impact": "action",
    "break": "action",
    "shatter": "action",
    "slide": "action",
    "drag": "action",
    "rub": "action",
    "friction": "action",
    "scratch": "action",
    "roll": "action",
    "shake": "action",
    "explosion": "action",
    "push": "action",
    "pull": "action",
    "open": "action",
    "close": "action",
    "shut": "action",
    "closing": "action",
    "stop": "action",
    "idle": "action",
    "rev": "action",
    "tear": "action",
    "rip": "action",
    "sand": "action",
    "burst": "action",
    "tone": "acoustic",
    "room": "acoustic",
    "wolf": "creature_sound",
    "howl": "creature_sound",
    "roar": "creature_sound",
    "growl": "creature_sound",
    "birds": "creature_sound",
    "insects": "creature_sound",
    "magic": "design",
    "energy": "design",
    "hex": "design",
    "hextech": "design",
    "gemstone": "design",
    "crystal": "design",
    "reverberant": "modifier",
    "exterior": "modifier",
    "interior": "modifier",
    "outdoor": "modifier",
    "underwater": "modifier",
    "empty": "modifier",
    "single": "modifier",
    "short": "modifier",
    "long": "modifier",
    "fast": "modifier",
    "slow": "modifier",
    "hard": "modifier",
    "soft": "modifier",
}


@dataclass(frozen=True)
class SlotTerm:
    token: str
    slot: str
    source: str = "compose"
    group: int = -1


@dataclass(frozen=True)
class AssemblyResult:
    text: str
    slots: list[dict[str, str]]
    assembled_order: list[str]
    reorder_reason: str


def infer_slot(token: str, hint: str | None = None) -> str:
    normalized_hint = (hint or "").replace("fx_", "").strip().lower()
    if normalized_hint in SLOT_ORDER:
        return normalized_hint
    words = [w.lower() for w in WORD_RE.findall(token)]
    if not words:
        return "unknown"
    scored: dict[str, int] = {}
    for word in words:
        slot = TOKEN_SLOT_OVERRIDES.get(word)
        if slot:
            scored[slot] = scored.get(slot, 0) + 1
    if scored:
        return max(scored.items(), key=lambda item: item[1])[0]
    return "unknown"


def split_slot_terms(
    text: str, slot: str, source: str = "compose", group: int = -1
) -> list[SlotTerm]:
    terms: list[SlotTerm] = []
    for word in WORD_RE.findall(text):
        word_slot = infer_slot(word)
        terms.append(
            SlotTerm(
                _title_word(word),
                word_slot if word_slot != "unknown" else slot,
                source,
                group,
            )
        )
    return terms


def assemble_fx_name(
    terms: list[SlotTerm], preserve_order: bool = True
) -> AssemblyResult:
    term_groups: list[list[SlotTerm]] = []
    grouped: dict[int, list[SlotTerm]] = {}
    for term in terms:
        if term.group >= 0:
            grouped.setdefault(term.group, []).append(term)
        else:
            term_groups.append([term])
    term_groups.extend(grouped[key] for key in sorted(grouped))

    deduped_groups: list[list[SlotTerm]] = []
    seen_groups: set[tuple[str, ...]] = set()
    for group in term_groups:
        key = tuple(term.token.lower() for term in group)
        if key in seen_groups:
            continue
        deduped_groups.append(group)
        seen_groups.add(key)

    if preserve_order:
        ordered_groups = list(enumerate(deduped_groups))
    else:
        ordered_groups = sorted(
            enumerate(deduped_groups),
            key=lambda item: (_group_rank(item[1]), item[0]),
        )
    ordered_terms = [term for _idx, group in ordered_groups for term in group]
    original = [term.token for group in deduped_groups for term in group]
    assembled = [term.token for term in ordered_terms]
    reason = "slot_order" if not preserve_order and assembled != original else "preserved"
    return AssemblyResult(
        text=" ".join(assembled),
        slots=[
            {"token": term.token, "slot": term.slot, "source": term.source}
            for term in ordered_terms
        ],
        assembled_order=assembled,
        reorder_reason=reason,
    )


def _slot_rank(slot: str) -> int:
    try:
        return SLOT_ORDER.index(slot)
    except ValueError:
        return SLOT_ORDER.index("unknown")


def _group_rank(group: list[SlotTerm]) -> int:
    return min(_slot_rank(term.slot) for term in group)


def _title_word(word: str) -> str:
    upper_words = {"fx", "sfx", "ucs", "bb", "ds"}
    if word.lower() in upper_words:
        return word.upper()
    return word[:1].upper() + word[1:].lower()
