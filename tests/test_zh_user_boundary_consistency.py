"""Grouping consistency for zh_user tokens after the safe-segmentation fix.

Background
----------
Spaced Chinese tokens are tagged ``zh_user`` by the tokenizer. Before the fix a
``zh_user`` token that missed an exact canonical lookup became a single whole
``unknown`` token, while the unspaced form was free to run sentence
segmentation. That made "木棍 敲打 钢门" and "木棍敲打钢门" diverge.

The fix lets ``zh_user`` tokens take a *safe* internal split: only multi-char
canonical / glossary tokens (or filler) may pass, never a single-char keep and
never a forbidden broad token. Unsafe splits fall back to whole-token unknown
review so nothing noisy leaks into the final FXName.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from fxengine.canonical_db import (
    DEFAULT_CANONICAL_PATH,
    FORBIDDEN_BROAD_ZH_TOKENS,
    CanonicalDB,
)
from fxengine.normalizer import FXNameNormalizer, normalize_fxname


def _ok_words(result) -> list[str]:
    """Lower-cased words contributed by ``ok`` tokens (order preserved)."""
    words: list[str] = []
    for token in result.tokens:
        if token.status == "ok" and token.canonical:
            words.extend(token.canonical.casefold().split())
    return words


def _has_unknown_zh(result) -> bool:
    return any("unknown_zh" in token.issues for token in result.tokens)


# ---------------------------------------------------------------------------
# A. Equivalent grouping should not blow up just because of spaces.
# ---------------------------------------------------------------------------

GROUP_A = [
    "木棍 敲打 钢门",
    "木棍敲打钢门",
    "木棍-敲打-钢门",
    "木棍_敲打_钢门",
    "木棍，敲打，钢门",
]


@pytest.mark.parametrize("text", GROUP_A)
def test_group_a_always_contains_wood_stick(text: str) -> None:
    result = normalize_fxname(text)
    assert "Wood Stick" in result.output_fxname


@pytest.mark.parametrize("text", GROUP_A)
def test_group_a_never_collapses_into_whole_input_unknown(text: str) -> None:
    """No variant may turn the whole phrase into one giant unknown blob."""
    result = normalize_fxname(text)
    stripped = text.replace(" ", "").replace("-", "").replace("_", "").replace("，", "")
    for token in result.tokens:
        if "unknown_zh" in token.issues:
            assert token.raw != stripped
            assert " " not in token.raw


def test_group_a_delimited_variants_are_identical() -> None:
    """Unspaced / dash / underscore / comma all run the same segmentation."""
    outputs = {normalize_fxname(text).output_fxname for text in GROUP_A[1:]}
    assert outputs == {"Wood Stick Knock Steel Door"}


def test_group_a_spaced_variant_keeps_token_boundaries() -> None:
    """Spaced form must not re-split a chunk into single characters.

    钢门 / 敲打 may stay whole-unknown (the table has no multi-char alias and a
    single-char split is forbidden), but they must never appear as standalone
    ok single-char tokens such as 钢 / 门 / 敲.
    """
    result = normalize_fxname(GROUP_A[0])
    for token in result.tokens:
        if token.status == "ok":
            assert len(token.raw) > 1, token.raw
    assert "Wood Stick" in result.output_fxname
    # Spaced output may be a subset of the delimited output, never a superset.
    spaced = set(_ok_words(result))
    delimited = set(_ok_words(normalize_fxname(GROUP_A[1])))
    assert spaced <= delimited


# ---------------------------------------------------------------------------
# B. Pairwise (spaced, unspaced) consistency: spaced must not be worse.
# ---------------------------------------------------------------------------

GROUP_B = [
    ("金属 摩擦 铁砧 刺耳的", "金属摩擦铁砧刺耳的"),
    ("门 打开 后 撞到 墙", "门打开后撞到墙"),
    ("纸张 揉皱 展开", "纸张揉皱展开"),
    ("金属盒 打开 合上", "金属盒打开合上"),
]


@pytest.mark.parametrize(("spaced", "unspaced"), GROUP_B)
def test_group_b_spaced_not_worse_than_unspaced(spaced: str, unspaced: str) -> None:
    spaced_result = normalize_fxname(spaced)
    unspaced_result = normalize_fxname(unspaced)

    # The spaced form must never invent tokens the unspaced form would not.
    assert set(_ok_words(spaced_result)) <= set(_ok_words(unspaced_result))


@pytest.mark.parametrize(("spaced", "unspaced"), GROUP_B)
def test_group_b_spaced_has_no_whole_input_unknown(spaced: str, unspaced: str) -> None:
    spaced_result = normalize_fxname(spaced)
    chunks = set(spaced.split())
    for token in spaced_result.tokens:
        if "unknown_zh" in token.issues:
            # Unknowns must line up with the explicit space-separated chunks the
            # user typed: never the whole merged input, and never a chunk that
            # was exploded into smaller pieces.
            assert token.raw != spaced.replace(" ", "")
            assert " " not in token.raw
            assert token.raw in chunks


def test_group_b_metal_friction_anvil_harsh_is_stable() -> None:
    spaced = normalize_fxname("金属 摩擦 铁砧 刺耳的")
    unspaced = normalize_fxname("金属摩擦铁砧刺耳的")

    assert spaced.output_fxname == "Metal Friction Anvil Harsh"
    assert unspaced.output_fxname == "Metal Friction Anvil Harsh"
    assert spaced.unknowns == []


def test_harsh_token_is_never_resplit_into_single_chars() -> None:
    result = normalize_fxname("金属 摩擦 铁砧 刺耳的")
    raws = [token.raw for token in result.tokens]
    assert "刺耳" in raws
    assert "刺" not in raws
    assert "耳" not in raws


# ---------------------------------------------------------------------------
# C. Safe-failure: forbidden broad tokens must never reach the final FXName.
# ---------------------------------------------------------------------------

FORBIDDEN_FAILURE_CASES = sorted(FORBIDDEN_BROAD_ZH_TOKENS)


@pytest.fixture(scope="module")
def normalizer() -> FXNameNormalizer:
    return FXNameNormalizer()


@pytest.mark.parametrize("raw", FORBIDDEN_FAILURE_CASES)
def test_forbidden_token_rejected_by_safe_segmentation(
    raw: str, normalizer: FXNameNormalizer
) -> None:
    """The zh_user safe-segmentation path must refuse every forbidden token."""
    assert normalizer.canonical_db.safe_segment_chinese_user_token(raw) is None


@pytest.mark.parametrize("raw", FORBIDDEN_FAILURE_CASES)
def test_forbidden_token_does_not_contribute_to_final(raw: str) -> None:
    result = normalize_fxname(raw)
    assert result.output_fxname == ""
    assert raw in result.unknowns or _has_unknown_zh(result)
    for token in result.tokens:
        if token.raw == raw:
            assert token.status != "ok"
        assert not token.contributes_to_fxname


@pytest.mark.parametrize("raw", FORBIDDEN_FAILURE_CASES)
def test_forbidden_token_stays_unknown_inside_a_phrase(raw: str) -> None:
    """As an explicit spaced neighbour it must not leak into the output."""
    result = normalize_fxname(f"金属 {raw}")
    assert result.output_fxname == "Metal"
    assert raw in result.unknowns


def test_cixerh_is_kept_whole_not_a_failure() -> None:
    """刺耳 is a legitimate multi-char keep: it maps to Harsh, never splits."""
    result = normalize_fxname("刺耳")
    assert result.output_fxname == "Harsh"
    raws = [token.raw for token in result.tokens]
    assert raws == ["刺耳"]


# ---------------------------------------------------------------------------
# D. Canonical table guard: no forbidden broad token may be a runtime keep,
#    and the safe path must never expose a single-char keep.
# ---------------------------------------------------------------------------


def _load_keep_rows() -> list[dict[str, str]]:
    path = Path(DEFAULT_CANONICAL_PATH)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [
            row
            for row in csv.DictReader(handle)
            if (row.get("review_status") or "keep").strip().lower() == "keep"
        ]


def test_no_forbidden_broad_token_is_runtime_keep() -> None:
    keep_raws = {(row.get("raw") or "").strip() for row in _load_keep_rows()}
    leaked = sorted(FORBIDDEN_BROAD_ZH_TOKENS & keep_raws)
    assert leaked == [], f"forbidden broad tokens promoted to keep: {leaked}"


def test_forbidden_broad_tokens_absent_from_runtime_index() -> None:
    db = CanonicalDB()
    for raw in FORBIDDEN_BROAD_ZH_TOKENS:
        assert raw not in db._zh_exact


def test_safe_segmentation_never_returns_single_char_keep() -> None:
    """Even where the table has single-char zh keeps (木/钢/门/铁/...), the
    safe zh_user path must reject any split that yields a single-char token."""
    db = CanonicalDB()
    for raw in ["钢门", "敲打", "撞到", "金属盒", "门墙", "钢铁"]:
        matches = db.safe_segment_chinese_user_token(raw)
        if matches is None:
            continue
        for match in matches:
            if match.source == "filler":
                continue
            assert len(match.raw) > 1, (raw, match.raw)
