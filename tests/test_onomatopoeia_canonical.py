"""Governance tests for the Chinese onomatopoeia / sound-symbolic batch.

These tests pin down the offline, reviewable behaviour required by
``docs/PROJECT_INVARIANTS.md``:

* multi-character onomatopoeia map to a single governed English token,
* reduplicated forms are never split into ambiguous single characters,
* single-character and review-only ambiguous forms never reach a final
  FXName (they must surface as needs_review / unknown instead),
* forbidden broad single tokens never produce a mapped canonical, and
* none of this relies on an NLLB / free-translation fallback.
"""

from __future__ import annotations

import pytest

from fxengine.normalizer import normalize_fxname


def _norm(text: str):
    result = normalize_fxname(text)
    # The whole point of this batch is that it stays offline and deterministic.
    assert result.debug["nllb_fallback_used"] is False
    return result


# --- Keep positives: each multi-char onomatopoeia maps to one governed token ---

STANDALONE_KEEP_CASES = [
    ("嘎吱", "Creak"),
    ("嘎吱嘎吱", "Creak"),
    ("咯吱", "Creak"),
    ("咯吱咯吱", "Creak"),
    ("咔哒", "Click"),
    ("咔嗒", "Click"),
    ("咔嚓", "Crack"),
    ("哐当", "Clank"),
    ("咣当", "Clang"),
    ("哐啷", "Clatter"),
    ("喀啦", "Clatter"),
    ("咔啦", "Clatter"),
    ("噼啪", "Crackle"),
    ("噼里啪啦", "Crackle"),
    ("嗡嗡", "Hum"),
    ("轰隆", "Rumble"),
    ("轰隆隆", "Rumble"),
    ("沙沙", "Rustle"),
    ("窸窣", "Rustle"),
    ("呼呼", "Whoosh"),
    ("嗖嗖", "Whoosh"),
    ("咚咚", "Thump"),
    ("咕噜", "Gurgle"),
    ("咕噜咕噜", "Gurgle"),
    ("滴答", "Tick"),
    ("滴滴答答", "Drip"),
    ("叮当", "Jingle"),
    ("叮咚", "Chime"),
    ("叮铃", "Jingle"),
    ("哔哔", "Beep"),
    ("嘶嘶", "Hiss"),
    ("呲呲", "Sizzle"),
    ("唰唰", "Swish"),
]


@pytest.mark.parametrize("raw, expected", STANDALONE_KEEP_CASES)
def test_standalone_onomatopoeia_maps_to_single_token(raw: str, expected: str) -> None:
    """Goal 1 & 3: standalone onomatopoeia output the canonical, never split."""
    result = _norm(raw)
    # Exact equality proves the phrase resolved as one unit and was not
    # re-segmented into single characters.
    assert result.output_fxname == expected
    assert any(
        token.decision == "mapped_canonical" and token.status == "ok"
        for token in result.tokens
    )


# --- Combination cases preserve user order: material/object then sound ---

COMBINATION_EXACT_CASES = [
    ("木门 嘎吱", "Wood Door Creak"),
    ("金属 哐当", "Metal Clank"),
    ("机器 嗡嗡", "Machine Hum"),
    ("火焰 噼啪", "Fire Crackle"),
    ("玻璃 咔嚓", "Glass Crack"),
    ("水下 咕噜", "Underwater Gurgle"),
]


@pytest.mark.parametrize("raw, expected", COMBINATION_EXACT_CASES)
def test_combination_preserves_user_order(raw: str, expected: str) -> None:
    """Goal 2: object/material stays in front of the onomatopoeia token."""
    result = _norm(raw)
    assert result.output_fxname == expected


COMBINATION_CONTAINS_CASES = [
    # An unknown prefix (风 / 树叶 / 钟表 / UI) must not block the sound mapping.
    ("风 呼呼", "Whoosh"),
    ("树叶 沙沙", "Rustle"),
    ("钟表 滴答", "Tick"),
    ("UI 哔哔", "Beep"),
]


@pytest.mark.parametrize("raw, expected", COMBINATION_CONTAINS_CASES)
def test_combination_keeps_sound_token(raw: str, expected: str) -> None:
    """Goal 2: even with an unknown companion, the sound token still maps."""
    result = _norm(raw)
    assert expected in result.output_fxname.split()


def test_reduplicated_phrase_is_not_split_into_single_guard() -> None:
    """Goal 3 & 4: 嗖嗖 -> Whoosh, while the single 嗖 must never output Whoosh."""
    assert _norm("嗖嗖").output_fxname == "Whoosh"
    single = _norm("嗖")
    assert "Whoosh" not in single.output_fxname
    assert single.output_fxname == ""


# --- Single-character onomatopoeia must never reach final FXName (Goal 4) ---

SINGLE_GUARD_CASES = [
    ("嗖", "Whoosh"),
    ("砰", "Bang"),
    ("啪", "Slap"),
    ("叮", "Jingle"),
]


@pytest.mark.parametrize("raw, forbidden_en", SINGLE_GUARD_CASES)
def test_single_onomatopoeia_does_not_reach_final(raw: str, forbidden_en: str) -> None:
    result = _norm(raw)
    assert result.output_fxname == ""
    assert forbidden_en not in result.output_fxname
    assert raw in result.unknowns
    assert result.quality == "needs_review"
    assert not any(
        token.decision == "mapped_canonical" and token.status == "ok"
        for token in result.tokens
    )


# --- Forbidden broad single tokens must never produce a mapped canonical ----

FORBIDDEN_BROAD_CASES = ["响", "打", "摔", "甩"]


@pytest.mark.parametrize("raw", FORBIDDEN_BROAD_CASES)
def test_forbidden_broad_token_not_mapped(raw: str) -> None:
    """Goal 5: broad tokens stay review/unknown, never status=ok mapped_canonical."""
    result = _norm(raw)
    assert result.output_fxname == ""
    assert not any(
        token.status == "ok" and token.decision == "mapped_canonical"
        for token in result.tokens
    )


# --- Ambiguous review-only phrases stay out of final output (Goal 6) --------

REVIEW_ONLY_CASES = [
    ("滋滋", ("Buzz", "Sizzle")),
    ("嗞嗞", ("Buzz", "Sizzle")),
    ("哗啦", ("Splash", "Rustle")),
    ("哗啦啦", ("Splash", "Rustle")),
    ("扑通", ("Thud", "Splash")),
    ("啪啪", ("Slap", "Clap")),
    ("嘟嘟", ("Beep", "Honk")),
    ("刷刷", ("Brush", "Swish")),
    ("砰砰", ("Bang", "Knock", "Impact")),
]


@pytest.mark.parametrize("raw, forbidden_en", REVIEW_ONLY_CASES)
def test_review_only_phrase_stays_out_of_final(raw: str, forbidden_en) -> None:
    result = _norm(raw)
    assert result.output_fxname == ""
    for word in forbidden_en:
        assert word not in result.output_fxname
    assert raw in result.unknowns
    assert result.quality == "needs_review"
