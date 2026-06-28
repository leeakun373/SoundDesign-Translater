"""Regression coverage for the authorized Batch Repair v0.1 rule set."""

from __future__ import annotations

import csv

import pytest

from fxengine.canonical_db import DEFAULT_CANONICAL_PATH
from fxengine.normalizer import FXNameNormalizer


PHRASE_REPAIRS = (
    ("打字", "Keyboard Typing"),
    ("打雷", "Thunder Rumble"),
    ("打滑轮胎", "Tire Skid"),
    ("车轮打滑", "Tire Skid"),
    ("转旋钮", "Knob Turn"),
    ("关保险柜", "Safe Close"),
    ("打火机", "Lighter Click"),
    ("打水漂", "Stone Skip Water"),
    ("打蛋", "Egg Whisk"),
    ("碰到麦架", "Mic Stand Bump"),
    ("碰倒玻璃杯", "Glass Cup Knock Over"),
    ("石头互碰", "Rock Clack"),
    ("塑料盒互碰", "Plastic Box Clack"),
    ("金属杆相碰", "Metal Rod Clank"),
    ("身体碰墙", "Body Bump Wall"),
    ("甩毛巾", "Towel Flap"),
    ("甩尾巴", "Tail Swing"),
    ("甩棍", "Stick Whoosh"),
    ("摔书", "Book Drop"),
    ("墙皮脱落", "Plaster Crumble"),
    ("拉链拉开再拉上", "Zipper Open Close"),
    ("水倒入杯中溅出", "Water Pour Splash"),
    ("摩擦皮革", "Leather Friction"),
    ("冰块刮擦冰砖", "Ice Scrape Ice Brick"),
    ("轮胎摩擦", "Tire Friction"),
    ("敲木门", "Wood Door Knock"),
    ("划船", "Boat Row"),
    ("刮风", "Wind Gust"),
    ("蹭衣服", "Cloth Rub"),
    ("骨头断裂", "Bone Crack"),
    ("石头碎裂", "Rock Crack"),
    ("金属断裂", "Metal Snap"),
    ("来回蹭地毯", "Carpet Rub"),
    ("来回摩擦毛毯", "Carpet Rub"),
    ("晃链条", "Chain Rattle"),
    ("轻碰桌边", "Table Bump"),
    ("苹果掉地上", "Apple Drop Floor"),
    ("开瓶盖", "Bottle Cap Open"),
    ("砖墙坍塌", "Brick Wall Collapse"),
    ("猫叫", "Cat Meow"),
    ("牛叫", "Cow Moo"),
    ("猪叫", "Pig Oink"),
    ("鸡叫", "Chicken Cluck"),
    ("海鸥叫", "Seagull Call"),
    ("鲸鱼叫声", "Whale Call"),
)

SAFE_ALIASES = (
    ("擦蹭", "Friction"),
    ("磨蹭", "Friction"),
    ("铁链", "Chain"),
    ("锁链", "Chain"),
    ("桌边", "Table"),
    ("滑过", "Slide"),
)


@pytest.fixture(scope="module")
def normalizer() -> FXNameNormalizer:
    return FXNameNormalizer()


@pytest.mark.parametrize(("raw", "expected"), PHRASE_REPAIRS)
def test_governed_phrase_repairs(
    normalizer: FXNameNormalizer, raw: str, expected: str
) -> None:
    result = normalizer.normalize(raw)
    assert result.output_fxname == expected
    assert result.unknowns == []
    assert result.quality == "pass"


@pytest.mark.parametrize(("raw", "expected"), SAFE_ALIASES)
def test_safe_natural_alias_repairs(
    normalizer: FXNameNormalizer, raw: str, expected: str
) -> None:
    result = normalizer.normalize(raw)
    assert result.output_fxname == expected
    assert result.unknowns == []


def test_connector_you_is_ignored_in_compound_action(
    normalizer: FXNameNormalizer,
) -> None:
    result = normalizer.normalize("门打开又关闭")
    assert result.output_fxname == "Door Open Close"
    assert "又" not in result.unknowns


@pytest.mark.parametrize("raw", ("打", "碰", "响", "甩"))
def test_ambiguous_single_characters_stay_review_only(
    normalizer: FXNameNormalizer, raw: str
) -> None:
    result = normalizer.normalize(raw)
    assert result.output_fxname == ""
    assert result.quality == "needs_review"
    assert result.unknowns == [raw]


def test_batch_repair_rows_are_manual_keep_rules_without_sound_suffixes() -> None:
    with DEFAULT_CANONICAL_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if "batch_repair_v0.1" in (row["note"] or "")]
    assert len(rows) == len(PHRASE_REPAIRS) + len(SAFE_ALIASES)
    assert {row["review_status"] for row in rows} == {"keep"}
    assert {row["source"] for row in rows} == {"manual"}
    alias_raws = {raw for raw, _canonical in SAFE_ALIASES}
    assert not any(
        row["raw"] in alias_raws and row["raw"].endswith(("声", "音"))
        for row in rows
    )
