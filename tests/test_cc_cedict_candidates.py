"""Tests for the CC-CEDICT offline weak-candidate layer (v0.1).

These tests use a tiny in-memory fixture index. They MUST NOT depend on the real
125k-entry CC-CEDICT snapshot, and they assert the review-only invariants:

* single-character / forbidden-broad tokens never become ``promote_candidate``;
* a candidate is only proposed when the BOOM target supports it.
"""

from __future__ import annotations

import gzip
import hashlib

import pytest

from fxengine.canonical_db import DEFAULT_CANONICAL_PATH
from glossary.cc_cedict import (
    FORBIDDEN_BROAD_TOKENS,
    CEDictIndex,
)

TARGET = "Heavy Wood Wardrobe Slide Slow Creak"

FIXTURE_LINES = [
    "衣櫃 衣柜 [yi1 gui4] /wardrobe/closet/",
    "木製 木制 [mu4 zhi4] /wooden/made of wood/",
    "重型 重型 [zhong4 xing2] /heavy/heavy-duty/",
    "打 打 [da3] /to hit/to beat/",
    "響 响 [xiang3] /to make a sound/to ring/",
    "開 开 [kai1] /to open/",
    "杯 杯 [bei1] /cup/classifier for drinks/",
]


@pytest.fixture()
def index() -> CEDictIndex:
    return CEDictIndex.from_lines(FIXTURE_LINES)


def _canonicals(result: dict) -> list[str]:
    return [c.canonical for c in result["candidates"]]


def test_wardrobe_promote_candidate(index: CEDictIndex) -> None:
    result = index.propose_for_target("衣柜", TARGET)
    assert result["status"] == "promote_candidate"
    assert "Wardrobe" in _canonicals(result)


def test_wood_promote_candidate(index: CEDictIndex) -> None:
    result = index.propose_for_target("木制", TARGET)
    assert result["status"] == "promote_candidate"
    assert "Wood" in _canonicals(result)


def test_heavy_promote_candidate(index: CEDictIndex) -> None:
    result = index.propose_for_target("重型", TARGET)
    assert result["status"] == "promote_candidate"
    assert "Heavy" in _canonicals(result)


def test_da_single_char_blocked(index: CEDictIndex) -> None:
    result = index.propose_for_target("打", "Hit")
    assert result["status"] in {"blocked", "review"}
    assert result["status"] != "promote_candidate"


def test_xiang_not_promoted(index: CEDictIndex) -> None:
    result = index.propose_for_target("响", "Ring")
    assert result["status"] != "promote_candidate"


def test_kai_not_promoted(index: CEDictIndex) -> None:
    result = index.propose_for_target("开", "Open")
    assert result["status"] != "promote_candidate"


def test_bei_not_promoted(index: CEDictIndex) -> None:
    result = index.propose_for_target("杯", "Cup")
    assert result["status"] != "promote_candidate"


def test_target_not_supported_is_review(index: CEDictIndex) -> None:
    result = index.propose_for_target("衣柜", "Metal Door Impact")
    assert result["status"] == "review"
    assert result["status"] != "promote_candidate"


def test_all_forbidden_broad_tokens_blocked(index: CEDictIndex) -> None:
    for token in FORBIDDEN_BROAD_TOKENS:
        result = index.propose_for_target(token, "Hit Impact Ring Open Cup")
        assert result["status"] == "blocked"
        assert result["candidates"] == []


def test_single_char_never_promotes_even_with_matching_target(
    index: CEDictIndex,
) -> None:
    # 杯 -> cup, target literally contains Cup, but single char is blocked.
    result = index.propose_for_target("杯", "Heavy Cup Drop")
    assert result["status"] == "blocked"
    assert result["candidates"] == []


def test_candidates_supported_by_target_filters(index: CEDictIndex) -> None:
    supported = index.candidates_supported_by_target("衣柜", TARGET)
    canon = [c.canonical for c in supported]
    assert "Wardrobe" in canon
    assert "Closet" not in canon  # not present in the target string


def test_lookup_blocked_tokens_return_empty(index: CEDictIndex) -> None:
    assert index.lookup("杯") == []
    assert index.lookup("打") == []


def test_from_file_reads_gz(tmp_path) -> None:
    gz_path = tmp_path / "cedict_fixture.u8.gz"
    with gzip.open(gz_path, "wt", encoding="utf-8") as handle:
        handle.write("\n".join(FIXTURE_LINES) + "\n")

    gz_index = CEDictIndex.from_file(gz_path)
    result = gz_index.propose_for_target("衣柜", TARGET)
    assert result["status"] == "promote_candidate"
    assert "Wardrobe" in _canonicals(result)


def test_from_file_reads_u8(tmp_path) -> None:
    u8_path = tmp_path / "cedict_fixture.u8"
    u8_path.write_text("\n".join(FIXTURE_LINES) + "\n", encoding="utf-8")

    u8_index = CEDictIndex.from_file(u8_path)
    result = u8_index.propose_for_target("衣柜", TARGET)
    assert result["status"] == "promote_candidate"
    assert "Wardrobe" in _canonicals(result)


def test_layer_does_not_modify_canonical_csv(index: CEDictIndex) -> None:
    before = hashlib.sha256(DEFAULT_CANONICAL_PATH.read_bytes()).hexdigest()
    index.propose_for_target("衣柜", TARGET)
    index.propose_for_target("木制", TARGET)
    index.lookup("打")
    after = hashlib.sha256(DEFAULT_CANONICAL_PATH.read_bytes()).hexdigest()
    assert before == after
