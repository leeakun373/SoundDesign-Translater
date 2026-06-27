"""FXName Normalize-mode regression coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine import EN_LANG, ZH_LANG, NllbTranslator, TranslationError
from glossary.boom_style import BoomStyleIndex
from glossary.matcher import GlossaryMatcher


ROOT = Path(__file__).resolve().parents[1]


class NormalizeTranslator(NllbTranslator):
    def __init__(self) -> None:
        super().__init__()
        self._translator = object()
        self._tokenizer = object()
        self._glossary = GlossaryMatcher()
        self._boom_style = BoomStyleIndex(ROOT / "tests" / "__missing_boom_style.sqlite")
        self.nllb_calls: list[str] = []

    def _nllb_translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        self.nllb_calls.append(text)
        return "How Can I Help You"


def test_basic_chinese_uses_canonical_tokens_in_order() -> None:
    translator = NormalizeTranslator()
    result = translator.translate_fxname("木门滑开")

    assert result.text == "Wood Door Slide Open"
    assert result.src_lang == ZH_LANG
    assert result.tgt_lang == EN_LANG
    assert result.debug["normalization_mode"] == "normalize"
    assert result.debug["preserve_order"] is True
    assert result.debug["reorder_reason"] == "preserved"
    assert translator.nllb_calls == []


def test_mixed_tokens_preserve_input_order_and_title_case() -> None:
    translator = NormalizeTranslator()
    result = translator.translate_fxname("door 推开 wood")

    assert result.text == "Door Push Open Wood"
    assert result.debug["assembled_order"] == ["Door", "Push", "Open", "Wood"]
    assert translator.nllb_calls == []


def test_oral_wrapper_is_removed_without_unknown_residue() -> None:
    translator = NormalizeTranslator()
    result = translator.translate_fxname("请帮我做一个木门滑开的声音")

    assert result.text == "Wood Door Slide Open"
    assert result.debug["unknown_zh"] == []
    assert result.debug["quality"] == "pass"


def test_chat_pollution_is_rejected_from_final_output() -> None:
    translator = NormalizeTranslator()
    result = translator.translate_fxname("木门 oh my god 滑开")

    assert result.text == "Wood Door Slide Open"
    assert "oh my god" in result.debug["rejected_unsafe_fragments"]
    assert "unsafe_fragment_rejected" in result.debug["issues"]
    assert result.debug["quality"] == "needs_review"


def test_unknown_is_reviewed_and_never_generated_by_nllb() -> None:
    translator = NormalizeTranslator()
    result = translator.translate_fxname("木门夔魍滑开")

    assert result.text == "Wood Door Slide Open"
    assert result.debug["unknown_zh"] == ["夔魍"]
    assert "unknown_zh" in result.debug["issues"]
    assert result.debug["quality"] == "needs_review"
    assert translator.nllb_calls == []
    assert "How Can I Help You" not in result.text


def test_pure_english_fxname_is_normalized_to_english() -> None:
    translator = NormalizeTranslator()
    result = translator.translate_fxname("metal door impact")

    assert result.text == "Metal Door Impact"
    assert result.src_lang == EN_LANG
    assert result.tgt_lang == EN_LANG
    assert translator.nllb_calls == []


def test_missing_glossary_fails_closed_without_nllb() -> None:
    translator = NormalizeTranslator()
    translator._glossary = None

    with pytest.raises(TranslationError, match="requires professional mode"):
        translator.translate_fxname("木门夔魍滑开")
    assert translator.nllb_calls == []
