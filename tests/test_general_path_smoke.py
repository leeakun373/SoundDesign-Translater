"""Minimal smoke coverage for the General versus FXName execution boundary."""

from __future__ import annotations

from pathlib import Path

from engine import EN_LANG, ZH_LANG, NllbTranslator, TaskMode, TranslateMode
from glossary.boom_style import BoomStyleIndex
from glossary.matcher import GlossaryMatcher


class GeneralPathProbe(NllbTranslator):
    def __init__(self) -> None:
        super().__init__()
        self._translator = object()
        self._tokenizer = object()
        self._glossary = GlossaryMatcher()
        self._boom_style = BoomStyleIndex(
            Path(__file__).resolve().parent / "__missing_general_smoke_boom.sqlite"
        )
        self.nllb_calls: list[tuple[str, str, str]] = []

    def _nllb_translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        self.nllb_calls.append((text, src_lang, tgt_lang))
        return "General Translation Output"


def test_general_path_keeps_nllb_while_fxname_unknown_does_not_use_it() -> None:
    translator = GeneralPathProbe()

    general = translator.translate_general(
        "你好世界",
        src_lang=ZH_LANG,
        tgt_lang=EN_LANG,
        mode=TranslateMode.SENTENCE,
    )

    assert general.task_mode == TaskMode.GENERAL.value
    assert general.debug["task_mode"] == TaskMode.GENERAL.value
    assert general.text == "General Translation Output"
    assert translator.nllb_calls == [("你好世界", ZH_LANG, EN_LANG)]

    translator.nllb_calls.clear()
    fxname = translator.translate_fxname(
        "kuang",
        src_lang=EN_LANG,
        tgt_lang=EN_LANG,
        mode=TranslateMode.SENTENCE,
    )

    assert fxname.task_mode == TaskMode.FXNAME.value
    assert fxname.text == ""
    assert fxname.debug["nllb_fallback_used"] is False
    assert translator.nllb_calls == []
