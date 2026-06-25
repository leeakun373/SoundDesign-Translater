#!/usr/bin/env python3
"""Unit tests for BOOM style index builder cleaning and weighting."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from build_boom_style_index import (  # noqa: E402
    FIELD_WEIGHTS,
    _accumulate_text_stats,
    _extract_clean_tokens,
    _is_clean_phrase,
    _is_noise_token,
)


def test_noise_tokens_filtered():
    blocked = [
        "alck",
        "ae",
        "st",
        "ds13",
        "co100k",
        "sanken",
        "mono",
        "microphone",
        "ambtrop",
        "anmlaqua",
        "creasrce",
    ]
    for token in blocked:
        assert _is_noise_token(token), f"expected noise: {token}"

    allowed = ["animal", "room", "tone", "impact", "door", "ambience", "movement"]
    for token in allowed:
        assert not _is_noise_token(token), f"expected style token: {token}"


def test_technical_phrases_rejected():
    blocked = [
        "high frequency response",
        "mono sanken co100k",
        "sanken co100k high",
        "co100k high frequency",
        "frequency response",
    ]
    for phrase in blocked:
        assert not _is_clean_phrase(phrase), f"expected blocked phrase: {phrase}"


def test_style_phrases_accepted():
    accepted = [
        "room tone",
        "white noise",
        "tree debris",
        "box scrape",
        "door impact",
        "animal movement",
    ]
    for phrase in accepted:
        assert _is_clean_phrase(phrase), f"expected clean phrase: {phrase}"


def test_field_weights_and_exclusions():
    clean_tokens: Counter[str] = Counter()
    clean_filename_tokens: Counter[str] = Counter()
    clean_phrases: Counter[str] = Counter()
    clean_filename_phrases: Counter[str] = Counter()
    raw_tokens: Counter[str] = Counter()
    raw_filename_tokens: Counter[str] = Counter()
    raw_phrases: Counter[str] = Counter()
    raw_filename_phrases: Counter[str] = Counter()

    record = {
        "fx_name": "Room Tone Wind",
        "filename": "AMB_Room_Tone_Wind.wav",
        "description": "Calm room tone with subtle wind",
        "keywords": "room tone wind",
        "category": "AMBIENCE",
        "subcategory": "ROOM",
        "library": "Roomtones Europe",
        "microphone": "Schoeps ORTF mono sanken co100k high frequency response",
    }

    _accumulate_text_stats(
        record,
        clean_tokens,
        clean_filename_tokens,
        clean_phrases,
        clean_filename_phrases,
        raw_tokens,
        raw_filename_tokens,
        raw_phrases,
        raw_filename_phrases,
    )

    assert clean_tokens["room"] == (
        FIELD_WEIGHTS["fx_name"]
        + FIELD_WEIGHTS["filename"]
        + FIELD_WEIGHTS["description"]
        + FIELD_WEIGHTS["keywords"]
        + FIELD_WEIGHTS["subcategory"]
    )
    assert clean_tokens["tone"] >= FIELD_WEIGHTS["fx_name"]
    assert "sanken" not in clean_tokens
    assert "co100k" not in clean_tokens
    assert "mono" not in clean_tokens
    assert "library" not in clean_tokens
    assert _is_clean_phrase("room tone")
    assert "room tone" in clean_phrases
    assert "high frequency response" not in clean_phrases


def test_clean_tokens_from_fx_name():
    tokens = _extract_clean_tokens("Pre Dawn Breeze Birds AMBTrop_CLOUDFOREST")
    assert "pre" in tokens
    assert "breeze" in tokens
    assert "birds" in tokens
    assert "ambtrop" not in tokens
