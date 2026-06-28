"""Regression coverage for the authorized Batch Repair v0.2 rule set."""

from __future__ import annotations

import csv

import pytest

from fxengine.canonical_db import DEFAULT_CANONICAL_PATH
from fxengine.normalizer import FXNameNormalizer


PHRASE_REPAIRS = (
    ("铃响", "Bell Ring"),
    ("抽屉拉开又关上", "Drawer Open Close"),
    ("警报响", "Alarm Ring"),
    ("金属片响", "Metal Sheet Rattle"),
    ("硬币响", "Coin Jingle"),
    ("链条响", "Chain Rattle"),
    ("风扇响", "Fan Whir"),
    ("肚子响", "Stomach Growl"),
    ("甩水", "Water Flick"),
    ("甩刀", "Knife Whoosh"),
    ("甩手", "Hand Whoosh"),
    ("甩门", "Door Slam"),
    ("甩绳子", "Rope Swing"),
    ("门打开后撞到墙", "Door Open Impact Wall"),
    ("拿起杯子放下", "Cup Pick Up Put Down"),
    ("金属盒打开合上", "Metal Box Open Close"),
    ("纸张揉皱展开", "Paper Crumple Unfold"),
    ("布料甩动落地", "Cloth Flap Drop"),
    ("陶瓷破碎", "Ceramic Shatter"),
    ("电话铃声", "Telephone Bell"),
    ("风声呼啸", "Wind Whoosh"),
    ("欢呼声", "Cheer"),
    ("战场呐喊", "Battle Shout"),
    ("僵尸呻吟", "Zombie Groan"),
    ("高跟鞋踩地", "High Heel Footstep"),
    ("闪光灯充能", "Camera Flash Charge"),
    ("溪流潺潺", "Stream Flow"),
    ("电钻钻孔", "Power Drill Drilling"),
    ("刮擦铁板", "Metal Plate Scrape"),
    ("打磨金属", "Metal Grind"),
    ("轻碰麦克风", "Mic Bump"),
    ("划玻璃", "Glass Scratch"),
    ("蹭地板", "Floor Scuff"),
    ("滑板滑行", "Skateboard Roll"),
    ("锤子砸铁板", "Hammer Hit Metal Plate"),
    ("车辆碰撞", "Car Crash"),
)

INTENTIONALLY_UNRESOLVED = (
    "门响",
    "水管响",
    "打电话",
    "打包",
    "甩出去",
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


@pytest.mark.parametrize("raw", INTENTIONALLY_UNRESOLVED)
def test_context_dependent_phrases_remain_review_only(
    normalizer: FXNameNormalizer, raw: str
) -> None:
    result = normalizer.normalize(raw)
    assert result.quality == "needs_review"


@pytest.mark.parametrize("raw", ("打", "碰", "响", "甩", "摔"))
def test_ambiguous_single_characters_have_no_runtime_output(
    normalizer: FXNameNormalizer, raw: str
) -> None:
    result = normalizer.normalize(raw)
    assert result.output_fxname == ""
    assert result.quality == "needs_review"
    assert result.unknowns == [raw]


def test_batch_repair_rows_are_manual_and_review_governed() -> None:
    with DEFAULT_CANONICAL_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = [
            row
            for row in csv.DictReader(handle)
            if "batch_repair_v0.2" in (row["note"] or "")
        ]

    assert len(rows) == len(PHRASE_REPAIRS) + 1
    assert {row["source"] for row in rows} == {"manual"}
    assert sum(row["review_status"] == "keep" for row in rows) == len(PHRASE_REPAIRS)
    review_row = next(row for row in rows if row["raw"] == "摔")
    assert review_row["review_status"] == "review"
    assert review_row["canonical"] == ""
