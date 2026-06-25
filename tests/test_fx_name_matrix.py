#!/usr/bin/env python3
"""Matrix tests for zh->en FX-name compose and validation."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from glossary.fx_name import validate_fx_name
from glossary.matcher import GlossaryMatcher
from glossary.zh_compose import compose_zh_to_en_debug
from engine import EN_LANG, ZH_LANG, NllbTranslator


@dataclass(frozen=True)
class FxCase:
    input: str
    required_tokens: list[str]
    forbidden_tokens: list[str] = field(default_factory=list)
    required_any: list[list[str]] = field(default_factory=list)
    before: list[tuple[str, str]] = field(default_factory=list)
    not_sentence: bool = True


CASES = [
    FxCase("木门滑开", ["Wood", "Door", "Slide", "Open"], ["Front"]),
    FxCase("玻璃门滑开", ["Glass", "Door", "Slide", "Open"], ["Front"]),
    FxCase("倒水入杯", ["Water", "Pour", "Cup"]),
    FxCase("轮胎摩擦", ["Tire"], required_any=[["Rub", "Friction"]]),
    FxCase("锯木", ["Saw", "Wood"]),
    FxCase("塑料盒掉落", ["Plastic", "Box", "Drop"], before=[("Box", "Drop")]),
    FxCase("水流过石头", ["Water", "Flow", "Stone"]),
    FxCase("木头 滑开", ["Wood", "Slide"], ["Front"]),
    FxCase("木门 滑开", ["Wood", "Door", "Slide"], ["Front"]),
    FxCase("前门 滑开", ["Front", "Door", "Slide"], []),
    FxCase("木门 推开", ["Wood", "Door", "Push", "Open"], ["Front"]),
    FxCase("木门 拉开", ["Wood", "Door", "Pull", "Open"], ["Front"]),
    FxCase("狼嚎火箭", ["Wolf", "Howl", "Rocket"]),
    FxCase("火箭狼嚎飞过", ["Rocket", "Wolf", "Howl", "Flyby"]),
    FxCase("海克斯宝石", [], required_any=[["Hex", "Hextech"], ["Gemstone", "Crystal"]]),
    FxCase(
        "海克斯宝石碎裂",
        [],
        required_any=[["Hex", "Hextech"], ["Gemstone", "Crystal"], ["Shatter", "Break"]],
    ),
]


class FakeTranslator(NllbTranslator):
    def __init__(self, matcher: GlossaryMatcher) -> None:
        super().__init__()
        self._translator = object()
        self._tokenizer = object()
        self._glossary = matcher

    def _nllb_translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        assert src_lang == ZH_LANG
        assert tgt_lang == EN_LANG
        return {"神秘": "Mystery"}.get(text, text)


def main() -> int:
    matcher = GlossaryMatcher()
    failures: list[str] = []

    for case in CASES:
        output, debug = compose_zh_to_en_debug(case.input, matcher)
        quality = validate_fx_name(case.input, output)
        lower_output = output.lower()

        missing = [
            token for token in case.required_tokens if token.lower() not in lower_output
        ]
        missing_any = [
            group
            for group in case.required_any
            if not any(token.lower() in lower_output for token in group)
        ]
        forbidden = [
            token for token in case.forbidden_tokens if token.lower() in lower_output
        ]
        order_errors = []
        for left, right in case.before:
            left_idx = lower_output.find(left.lower())
            right_idx = lower_output.find(right.lower())
            if left_idx == -1 or right_idx == -1 or left_idx > right_idx:
                order_errors.append(f"{left} before {right}")
        if missing or missing_any or forbidden or order_errors:
            failures.append(
                f"{case.input!r}: output={output!r}, missing={missing}, "
                f"missing_any={missing_any}, forbidden={forbidden}, "
                f"order_errors={order_errors}, debug={debug}"
            )
        if case.not_sentence and "natural_sentence" in quality.issues:
            failures.append(f"{case.input!r}: output looked like a sentence: {output!r}")
        if output.lower().startswith(("the ", "a ", "an ")):
            failures.append(f"{case.input!r}: output started with an article: {output!r}")

    low_info = validate_fx_name("木头 滑开", "Wood")
    if "low_information" not in low_info.issues:
        failures.append("'Wood' should be rejected as low information")

    natural = validate_fx_name("木头 滑开", "The Wood Slipped.")
    if "natural_sentence" not in natural.issues:
        failures.append("'The Wood Slipped.' should be rejected as a natural sentence")

    front = validate_fx_name("木门 滑开", "Front")
    if "forbidden:Front" not in front.issues:
        failures.append("'Front' should be forbidden unless input explicitly says 前门")

    for src in ("油门", "外面", "门外", "门口"):
        door_quality = validate_fx_name(src, "Exterior")
        if "missing:Door" in door_quality.issues:
            failures.append(f"{src!r} should not require Door: {door_quality.issues}")

    for src, output in (
        ("心跳", "Heartbeat"),
        ("咳嗽", "Cough"),
        ("打喷嚏", "Sneeze"),
        ("掌声", "Applause"),
    ):
        event_quality = validate_fx_name(src, output)
        if "low_information" in event_quality.issues:
            failures.append(
                f"{src!r} single event should not be low_information: {event_quality.issues}"
            )

    translator = FakeTranslator(matcher)
    direct = translator.translate_fxname("木门滑开")
    if direct.text != "Wood Door Slide Open":
        failures.append(f"木门滑开 should remain Wood Door Slide Open, got {direct.text!r}")
    direct_lower = direct.text.lower()
    for token in ("wood", "door", "slide", "open"):
        if token not in direct_lower:
            failures.append(f"engine direct compose missed {token}: {direct.text!r}")
    if direct.debug.get("hybrid_fallback"):
        failures.append(f"engine should not need fallback for full coverage: {direct.debug}")

    hybrid = translator.translate_fxname("木门 神秘滑开")
    if not hybrid.debug.get("hybrid_fallback"):
        failures.append(f"engine should use fallback with unknown zh: {hybrid.debug}")
    for token in ("wood", "door", "slide", "mystery"):
        if token not in hybrid.text.lower():
            failures.append(f"engine hybrid missed {token}: {hybrid.text!r}")

    if failures:
        print("FX matrix failures:")
        for failure in failures:
            print("-", failure)
        return 1

    print(f"FX matrix PASS ({len(CASES)} compose cases + validator guards)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
