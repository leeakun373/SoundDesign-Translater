"""Explicit Chinese whitespace boundaries must survive FXName parsing."""

from __future__ import annotations

import pytest

from fxengine.canonical_db import cleanup_chinese_user_token
from fxengine.normalizer import FXNameNormalizer
from fxengine.tokenizer import FXTokenizer


def test_tokenizer_preserves_explicit_chinese_chunks() -> None:
    tokens = FXTokenizer().tokenize("金属 摩擦 铁砧 刺耳的")

    assert [(token.raw, token.kind) for token in tokens] == [
        ("金属", "zh_user"),
        ("摩擦", "zh_user"),
        ("铁砧", "zh_user"),
        ("刺耳的", "zh_user"),
    ]


@pytest.mark.parametrize(
    ("raw", "cleaned"),
    (
        ("刺耳的", "刺耳"),
        ("很刺耳的", "刺耳"),
        ("比较刺耳的", "刺耳"),
        ("有点刺耳的", "刺耳"),
        ("非常刺耳的", "刺耳"),
        ("然后", ""),
        ("请帮我翻译", ""),
        ("这个声音是", ""),
    ),
)
def test_user_token_cleanup_is_boundary_only(raw: str, cleaned: str) -> None:
    assert cleanup_chinese_user_token(raw) == cleaned


def test_spaced_chinese_user_tokens_use_exact_lookup() -> None:
    result = FXNameNormalizer().normalize("金属 摩擦 铁砧 刺耳的")

    assert result.output_fxname == "Metal Friction Anvil Harsh"
    assert result.quality == "pass"
    assert result.unknowns == []
    assert [token.raw for token in result.tokens] == ["金属", "摩擦", "铁砧", "刺耳"]
    assert "Stab" not in result.output_fxname
    assert "耳" not in [token.raw for token in result.tokens]


@pytest.mark.parametrize(
    "qualified",
    ("很刺耳的", "比较刺耳的", "有点刺耳的", "非常刺耳的"),
)
def test_qualified_user_token_cleanup_reaches_exact_canonical(
    qualified: str,
) -> None:
    result = FXNameNormalizer().normalize(f"金属 {qualified}")

    assert result.output_fxname == "Metal Harsh"
    assert result.quality == "pass"
    assert result.unknowns == []


def test_unknown_user_token_remains_whole_and_out_of_final() -> None:
    result = FXNameNormalizer().normalize("金属 未知刺耳感 摩擦")

    assert result.output_fxname == "Metal Friction"
    assert result.quality == "needs_review"
    assert result.unknowns == ["未知刺耳感"]
    assert "Stab" not in result.output_fxname


def test_single_high_risk_glossary_character_cannot_reach_final() -> None:
    result = FXNameNormalizer().normalize("刺")

    assert result.output_fxname == ""
    assert result.quality == "needs_review"
    assert result.unknowns == ["刺"]


def test_unspaced_long_chinese_still_uses_sentence_segmentation() -> None:
    result = FXNameNormalizer().normalize("金属摩擦铁砧刺耳")

    assert result.output_fxname == "Metal Friction Anvil Harsh"
    assert result.quality == "pass"


def test_filler_user_token_is_ignored_without_changing_neighbors() -> None:
    result = FXNameNormalizer().normalize("金属 然后 摩擦")

    assert result.output_fxname == "Metal Friction"
    assert result.quality == "pass"
