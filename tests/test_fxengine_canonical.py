"""Canonical Token Database v0.1 and review-policy coverage."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from fxengine.canonical_db import CANONICAL_SLOTS, CanonicalDB
from fxengine.normalizer import FXNameNormalizer
from fxengine.personal_dictionary import PersonalDictionary
from fxengine.preferences import PreferenceStore
from fxengine.scorer import BoomScorer
from fxengine.ui import FXNameEngineApp
from glossary.boom_style import BoomStyleIndex


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_CSV = ROOT / "fxengine" / "data" / "canonical_tokens.csv"
MANUAL_CASES_CSV = ROOT / "tests" / "fixtures" / "fxname_manual_cases.csv"


def _normalizer(dictionary: PersonalDictionary | None = None) -> FXNameNormalizer:
    return FXNameNormalizer(
        personal_dictionary=dictionary,
        scorer=BoomScorer(BoomStyleIndex(ROOT / "tests" / "__missing_canonical_boom.sqlite")),
    )


def test_canonical_csv_has_required_schema_coverage_and_unique_aliases() -> None:
    with CANONICAL_CSV.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert reader.fieldnames == [
        "raw",
        "canonical",
        "slot",
        "lang",
        "priority",
        "tags",
        "note",
    ]
    zh_rows = [row for row in rows if row["lang"] == "zh"]
    assert len(zh_rows) >= 120
    assert len({row["raw"] for row in zh_rows}) == len(zh_rows)
    assert set(Counter(row["slot"] for row in zh_rows)) == CANONICAL_SLOTS

    db = CanonicalDB()
    assert db.token_count == len(rows)
    assert db.slot_counts == dict(Counter(row["slot"] for row in rows))


def test_canonical_csv_precedes_glossary_for_same_alias() -> None:
    match = CanonicalDB().segment_chinese("金属")[0]

    assert match.canonical == "Metal"
    assert match.slot == "material"
    assert match.source == "canonical_csv"


def test_personal_dictionary_precedes_canonical_csv_inside_chinese_run(
    tmp_path: Path,
) -> None:
    dictionary = PersonalDictionary(tmp_path / "personal.json")
    dictionary.add_alias("金属", "Steel Alloy")

    result = _normalizer(dictionary).normalize("金属门撞击")

    assert result.output_fxname == "Steel Alloy Door Impact"
    assert result.tokens[0].source == "personal_map"


def test_personal_alias_can_be_removed_and_reloaded(tmp_path: Path) -> None:
    path = tmp_path / "personal.json"
    dictionary = PersonalDictionary(path)
    dictionary.add_alias("kuang", "Metal Impact")
    assert dictionary.remove_alias("kuang") is True
    assert dictionary.remove_alias("kuang") is False

    reloaded = PersonalDictionary(path)
    assert reloaded.resolve_entry("kuang") is None


def test_builtin_review_preferences() -> None:
    store = PreferenceStore()
    normalizer = _normalizer()

    assert store.names()[:4] == [
        "Default",
        "No Distance",
        "Strict Review",
        "Keep Raw Friendly",
    ]

    default = normalizer.normalize("kuang", store.get("Default"))
    strict = normalizer.normalize("kuang", store.get("Strict Review"))
    friendly = normalizer.normalize("kuang", store.get("Keep Raw Friendly"))
    shorthand = normalizer.normalize(
        "CO100K MKH8040", store.get("Keep Raw Friendly")
    )

    assert default.output_fxname == ""
    assert default.tokens[0].status == "unknown"
    assert default.quality == "needs_review"
    assert strict.output_fxname == ""
    assert strict.tokens[0].status == "unknown"
    assert strict.quality == "needs_review"
    assert friendly.output_fxname == "Kuang"
    assert friendly.tokens[0].status == "needs_review"
    assert friendly.tokens[0].issues == ["unknown_ascii"]
    assert friendly.quality == "needs_review"
    assert shorthand.output_fxname == "CO100K MKH8040"


def test_no_distance_reports_metadata_candidate_and_issue() -> None:
    result = _normalizer().normalize(
        "爆炸 5m", PreferenceStore().get("No Distance")
    )

    assert result.output_fxname == "Explosion"
    assert result.debug["metadata_candidates"] == ["5m"]
    assert "distance_excluded:5m" in result.issues
    assert result.quality == "needs_review"


def test_issue_display_format_is_readable() -> None:
    assert FXNameEngineApp._display_issue("unknown_ascii:kuang") == "unknown_ascii: kuang"
    assert FXNameEngineApp._display_issue("distance_excluded:5m") == "distance_excluded: 5m"
    assert (
        FXNameEngineApp._display_issue("unsafe_fragment_rejected")
        == "unsafe_fragment_rejected"
    )


def test_manual_fxname_cases() -> None:
    store = PreferenceStore()
    normalizer = _normalizer()
    profile_names = {
        "default": "Default",
        "no_distance": "No Distance",
        "strict_review": "Strict Review",
        "keep_raw_friendly": "Keep Raw Friendly",
    }
    with MANUAL_CASES_CSV.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) >= 50
    for row_number, row in enumerate(rows, start=2):
        profile = store.get(profile_names[row["mode"]])
        result = normalizer.normalize(row["input"], profile)
        assert result.output_fxname == row["expected"], (
            f"manual case row {row_number}: {row['input']!r} -> "
            f"{result.output_fxname!r}, expected {row['expected']!r}"
        )
        assert result.debug["nllb_fallback_used"] is False
