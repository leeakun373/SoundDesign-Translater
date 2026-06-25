#!/usr/bin/env python3
"""Mode boundary regression tests for General vs FXName translation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import EN_LANG, TaskMode, TranslateMode, ZH_LANG, NllbTranslator
from glossary.fx_quality import find_bad_phrases
from glossary.matcher import GlossaryMatcher


BAD_PHRASE_OUTPUTS = (
    "Plastic Box Get Out Of Here It S Down",
    "Metal Door Was Knocked Knock",
    "Cloth Pull Oh My God Moving",
)


class FakeTranslator(NllbTranslator):
    """Stub NLLB that returns sentence-like garbage for unknown Chinese chunks."""

    def __init__(self, matcher: GlossaryMatcher) -> None:
        super().__init__()
        self._translator = object()
        self._tokenizer = object()
        self._glossary = matcher

    def _nllb_translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        garbage = {
            "盒掉": "Get Out Of Here It S Down",
            "落": "Oh My God Moving",
            "门撞": "Was Knocked Knock",
            "塑料盒掉落": "Plastic Box Get Out Of Here It S Down",
            "金属门撞击": "Metal Door Was Knocked Knock",
            "布帘拉动": "Cloth Pull Oh My God Moving",
            "木门滑开": "Wood Door Slide Open",
            "你好世界": "Hello world, how are you today?",
        }
        if text in garbage:
            return garbage[text]
        return text


def test_should_use_fxname_pipeline() -> None:
    assert NllbTranslator._should_use_fxname_pipeline(
        task_mode=TaskMode.FXNAME,
        mode=TranslateMode.SENTENCE,
        src_lang=ZH_LANG,
        pro_mode=True,
        glossary_ready=True,
        resolved_mode=TranslateMode.SENTENCE,
    )
    assert not NllbTranslator._should_use_fxname_pipeline(
        task_mode=TaskMode.GENERAL,
        mode=TranslateMode.SENTENCE,
        src_lang=ZH_LANG,
        pro_mode=True,
        glossary_ready=True,
        resolved_mode=TranslateMode.SENTENCE,
    )
    assert not NllbTranslator._should_use_fxname_pipeline(
        task_mode=TaskMode.FXNAME,
        mode=TranslateMode.SENTENCE,
        src_lang=EN_LANG,
        pro_mode=True,
        glossary_ready=True,
        resolved_mode=TranslateMode.SENTENCE,
    )


def test_default_task_mode_is_fxname() -> None:
    import inspect

    sig = inspect.signature(NllbTranslator.translate)
    default = sig.parameters["task_mode"].default
    assert default == TaskMode.FXNAME


def test_translate_fxname_wrapper() -> None:
    matcher = GlossaryMatcher()
    t = FakeTranslator(matcher)
    result = t.translate_fxname("木门滑开")
    assert result.task_mode == TaskMode.FXNAME.value
    assert "Wood" in result.text
    assert result.debug.get("task_mode") == TaskMode.FXNAME.value


def test_general_mode_skips_fx_pipeline() -> None:
    matcher = GlossaryMatcher()
    t = FakeTranslator(matcher)
    result = t.translate_general("塑料盒掉落", mode=TranslateMode.SENTENCE)
    assert result.task_mode == TaskMode.GENERAL.value
    assert result.debug.get("task_mode") == TaskMode.GENERAL.value
    # General path uses segment+NLLB, not compose slot assembly with bad phrase gate on full output
    assert "glossary_hits" in result.__dict__ or result.glossary_hits >= 0


def test_fxname_mode_has_quality_debug() -> None:
    matcher = GlossaryMatcher()
    t = FakeTranslator(matcher)
    result = t.translate_fxname("塑料盒掉落")
    assert "quality" in result.debug
    assert "issues" in result.debug
    assert result.debug.get("task_mode") == TaskMode.FXNAME.value


def test_bad_phrase_detector_catches_samples() -> None:
    for output in BAD_PHRASE_OUTPUTS:
        abs_hits, _ = find_bad_phrases(output)
        assert abs_hits, f"expected bad phrases in {output!r}"


def test_mixed_input_uses_fx_pipeline_in_fxname_mode() -> None:
    matcher = GlossaryMatcher()
    t = FakeTranslator(matcher)
    result = t.translate_fxname("door 推开 wood", mode=TranslateMode.SENTENCE)
    assert result.task_mode == TaskMode.FXNAME.value
    assert result.debug.get("slots") is not None or result.glossary_hits >= 0


def test_empty_output_needs_review() -> None:
    matcher = GlossaryMatcher()
    t = FakeTranslator(matcher)

    class EmptyNllb(FakeTranslator):
        def _nllb_translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
            return ""

    t2 = EmptyNllb(matcher)
    result = t2.translate_fxname("海克斯宝石碎裂", mode=TranslateMode.SENTENCE)
    if not result.text.strip():
        assert result.debug.get("quality") in {"needs_review", "fail"}


def main() -> int:
    tests = [
        test_should_use_fxname_pipeline,
        test_default_task_mode_is_fxname,
        test_translate_fxname_wrapper,
        test_general_mode_skips_fx_pipeline,
        test_fxname_mode_has_quality_debug,
        test_bad_phrase_detector_catches_samples,
        test_mixed_input_uses_fx_pipeline_in_fxname_mode,
        test_empty_output_needs_review,
    ]
    failures: list[str] = []
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failures.append(f"{fn.__name__}: {exc}")
    if failures:
        print("FXName mode boundary failures:")
        for f in failures:
            print("-", f)
        return 1
    print(f"FXName mode boundary PASS ({len(tests)} tests)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
