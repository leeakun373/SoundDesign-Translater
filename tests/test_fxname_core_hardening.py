#!/usr/bin/env python3
"""SD FXName Core Hardening 0.1 — regression tests for FXName pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from glossary.fx_name import accept_nllb_fx_candidate
from glossary.fx_quality import find_bad_phrases
from glossary.matcher import GlossaryMatcher
from glossary.zh_compose import compose_zh_to_en_debug
from glossary.zh_normalize import normalize_fxname_input
from engine import EN_LANG, ZH_LANG, NllbTranslator


BAD_NLLB_CASES = [
    "Plastic Box Get Out Of Here It S Down",
    "Metal Door Was Knocked Knock",
    "Cloth Pull Oh My God Moving",
    "How Can I Help You",
]

BAD_INPUT_CASES = [
    "塑料 盒掉 落",
    "金属 门撞 击",
    "布帘拉动",
    "打磨",
    "连发",
]

DOOR_PHRASE_CASES = [
    ("打开关闭门", "Door Open Close"),
    ("开关门", "Door Open Close"),
    ("门打开关闭", "Door Open Close"),
]

GOOD_COMPOSE_CASES = [
    ("杯子掉落打碎", ["Cup", "Drop"], [["Shatter", "Break"]]),
    ("拖动摩擦停止", ["Drag"], [["Rub", "Friction"], ["Stop"]]),
    ("打开关闭门", ["Door", "Open", "Close"]),
    ("木桌撞击", ["Wooden", "Table", "Impact"]),
    ("纸袋撕裂", ["Paper", "Bag"], [["Tear", "Rip"]]),
    ("塑料盒掉落", ["Plastic", "Box", "Drop"]),
    ("金属门撞击", ["Metal", "Door", "Impact"]),
    ("玻璃门滑开", ["Glass", "Door", "Slide", "Open"]),
    ("引擎怠速轰油门", ["Engine", "Idle", "Rev"]),
    ("水流 过 石头", ["Water", "Flow", "Stone"]),
]

MIXED_CASES = [
    ("door 推开 wood", ["Wood", "Door", "Push", "Open"]),
    ("exterior 混响 room tone", ["Exterior", "Reverberant", "Room", "Tone"]),
    ("whoosh 飞过", ["Whoosh", "Flyby"]),
]

SPACING_PAIRS = [
    ("塑料 盒掉 落", "塑料盒掉落"),
    ("金属 门撞 击", "金属门撞击"),
]


class FakeTranslator(NllbTranslator):
    def __init__(self, matcher: GlossaryMatcher, nllb_map: dict[str, str] | None = None) -> None:
        super().__init__()
        self._translator = object()
        self._tokenizer = object()
        self._glossary = matcher
        self._nllb_map = nllb_map or {
            "神秘": "Mystery",
            "打磨": "How Can I Help You",
            "连发": "Hair",
            "过": "It S Over",
            "门撞": "Door Was Knocked",
        }

    def _nllb_translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        assert src_lang == ZH_LANG
        assert tgt_lang == EN_LANG
        return self._nllb_map.get(text, text)


def _contains_bad_phrase(output: str) -> list[str]:
    absolute, _ = find_bad_phrases(output)
    return absolute


def _has_tokens(output: str, required: list[str], any_groups: list[list[str]] | None = None) -> bool:
    lower = output.lower()
    if not all(tok.lower() in lower for tok in required):
        return False
    if any_groups:
        return all(any(t.lower() in lower for t in group) for group in any_groups)
    return True


def test_normalize_spacing() -> None:
    assert normalize_fxname_input("塑料 盒掉 落") == "塑料盒掉落"
    assert normalize_fxname_input("金属 门撞 击") == "金属门撞击"
    assert normalize_fxname_input("door 推开 wood") == "door 推开 wood"
    assert normalize_fxname_input("exterior 混响 room tone") == "exterior 混响 room tone"


def test_nllb_candidate_reject() -> None:
    for raw in BAD_NLLB_CASES:
        result = accept_nllb_fx_candidate(raw)
        assert result.fragment is None, f"should reject {raw!r}, got {result.fragment!r}"


def test_compose_door_phrases_exact() -> None:
    matcher = GlossaryMatcher()
    for inp, expected in DOOR_PHRASE_CASES:
        output, _ = compose_zh_to_en_debug(inp, matcher)
        assert output == expected, f"{inp!r} -> {output!r}, want {expected!r}"


def test_compose_good_cases() -> None:
    matcher = GlossaryMatcher()
    for inp, required, *rest in GOOD_COMPOSE_CASES:
        any_groups = rest[0] if rest else None
        output, _ = compose_zh_to_en_debug(inp, matcher)
        assert _has_tokens(output, required, any_groups), f"{inp!r} -> {output!r}"


def test_compose_spacing_equivalence() -> None:
    matcher = GlossaryMatcher()
    for spaced, compact in SPACING_PAIRS:
        out_spaced, _ = compose_zh_to_en_debug(spaced, matcher)
        out_compact, _ = compose_zh_to_en_debug(compact, matcher)
        assert out_spaced == out_compact, f"{spaced!r} vs {compact!r}: {out_spaced!r} != {out_compact!r}"


def test_engine_bad_phrase_prevention() -> None:
    matcher = GlossaryMatcher()
    translator = FakeTranslator(matcher)
    for inp in BAD_INPUT_CASES:
        result = translator.translate_fxname(inp)
        bad = _contains_bad_phrase(result.text)
        assert not bad, f"{inp!r} -> {result.text!r} contains bad phrases {bad}"


def test_engine_door_phrases_exact() -> None:
    matcher = GlossaryMatcher()
    translator = FakeTranslator(matcher)
    for inp, expected in DOOR_PHRASE_CASES:
        result = translator.translate_fxname(inp)
        assert result.text == expected, f"{inp!r} -> {result.text!r}, want {expected!r}"


def test_engine_good_outputs() -> None:
    matcher = GlossaryMatcher()
    translator = FakeTranslator(matcher)
    for inp, required, *rest in GOOD_COMPOSE_CASES:
        any_groups = rest[0] if rest else None
        result = translator.translate_fxname(inp)
        assert _has_tokens(result.text, required, any_groups), (
            f"{inp!r} -> {result.text!r}"
        )


def test_engine_mixed_english() -> None:
    matcher = GlossaryMatcher()
    translator = FakeTranslator(matcher)
    for inp, required in MIXED_CASES:
        result = translator.translate_fxname(inp)
        assert result.src_lang == ZH_LANG, f"{inp!r} should be zh->en, got {result.src_lang}"
        assert _has_tokens(result.text, required), f"{inp!r} -> {result.text!r}"
        assert not _contains_bad_phrase(result.text)


def test_task_mode_separation() -> None:
    matcher = GlossaryMatcher()
    translator = FakeTranslator(matcher)
    fx = translator.translate_fxname("木门滑开")
    assert fx.task_mode == "fxname"
    assert fx.debug.get("task_mode") == "fxname"
    general = translator.translate_general("木门滑开", mode="sentence")
    assert general.task_mode == "general"


def main() -> int:
    tests = [
        test_normalize_spacing,
        test_nllb_candidate_reject,
        test_compose_door_phrases_exact,
        test_compose_good_cases,
        test_compose_spacing_equivalence,
        test_engine_bad_phrase_prevention,
        test_engine_door_phrases_exact,
        test_engine_good_outputs,
        test_engine_mixed_english,
        test_task_mode_separation,
    ]
    failures: list[str] = []
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failures.append(f"{fn.__name__}: {exc}")
    if failures:
        print("FXName core hardening failures:")
        for f in failures:
            print("-", f)
        return 1
    print(f"FXName core hardening PASS ({len(tests)} tests)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
