"""Canonical Token Database v0.1 and review-policy coverage."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import replace
from pathlib import Path

from fxengine.canonical_db import CANONICAL_SLOTS, CanonicalDB
from fxengine.models import BoomScoreResult, FXToken
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

    dictionary.add_alias("木桌", "Hero Table")
    fallback_override = _normalizer(dictionary).normalize("木桌撞击")
    assert fallback_override.output_fxname == "Hero Table Impact"
    assert fallback_override.tokens[0].source == "personal_map"


def test_personal_alias_can_be_removed_and_reloaded(tmp_path: Path) -> None:
    path = tmp_path / "personal.json"
    dictionary = PersonalDictionary(path)
    normalizer = _normalizer(dictionary)
    before = normalizer.normalize("kuang")
    assert before.output_fxname == ""
    assert before.quality == "needs_review"

    dictionary.add_alias("kuang", "Metal Impact")
    mapped = normalizer.normalize("kuang")
    assert mapped.output_fxname == "Metal Impact"
    assert mapped.tokens[0].source == "personal_map"

    assert dictionary.remove_alias("kuang") is True
    assert dictionary.remove_alias("kuang") is False
    after = normalizer.normalize("kuang")
    assert after.output_fxname == ""
    assert after.quality == "needs_review"

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
    assert friendly.output_fxname == ""
    assert friendly.tokens[0].status == "unknown"
    assert friendly.tokens[0].issues == ["unknown_ascii"]
    assert friendly.quality == "needs_review"
    assert shorthand.output_fxname == ""
    assert shorthand.debug["metadata_candidates"] == ["CO100K", "MKH8040"]
    assert all(token.status == "ignored" for token in shorthand.tokens)


def test_keep_raw_rules_distinguish_fx_onomatopoeia_and_technical_tokens() -> None:
    profile = PreferenceStore().get("Keep Raw Friendly")
    normalizer = _normalizer()

    common = normalizer.normalize(
        "whoosh impact hit scrape rattle creak crack blast explosion tail",
        profile,
    )
    onomatopoeia = normalizer.normalize("kuang duang zila kacha peng", profile)
    technical = normalizer.normalize("CO100K MKH8040 416 MS AB 192k", profile)

    assert common.output_fxname == (
        "Whoosh Impact Hit Scrape Rattle Creak Crack Blast Explosion Tail"
    )
    assert onomatopoeia.output_fxname == ""
    assert onomatopoeia.unknowns == ["kuang", "duang", "zila", "kacha", "peng"]
    assert technical.output_fxname == ""
    assert technical.debug["metadata_candidates"] == [
        "CO100K",
        "MKH8040",
        "416",
        "MS",
        "AB",
        "192k",
    ]


def test_personal_dictionary_can_explicitly_map_technical_token(tmp_path: Path) -> None:
    dictionary = PersonalDictionary(tmp_path / "personal.json")
    dictionary.add_alias("CO100K", "Recorder")

    result = _normalizer(dictionary).normalize("CO100K impact")

    assert result.output_fxname == "Recorder Impact"
    assert result.debug["metadata_candidates"] == []
    assert result.tokens[0].source == "personal_map"


def test_boom_suggestion_cannot_replace_manual_case_final() -> None:
    class SuggestingScorer:
        def score(self, text: str) -> BoomScoreResult:
            return BoomScoreResult(
                input_text=text,
                confidence=1.0,
                suggestion="Heavy Boom Replacement",
                phrase_hits=["boom replacement"],
                available=True,
            )

    result = FXNameNormalizer(scorer=SuggestingScorer()).normalize("金属门撞击")

    assert result.output_fxname == "Metal Door Impact"
    assert result.boom_suggestion == "Heavy Boom Replacement"
    assert result.suggestions == ["Heavy Boom Replacement"]


def test_no_distance_reports_metadata_candidate_and_issue() -> None:
    result = _normalizer().normalize(
        "爆炸 5m", PreferenceStore().get("No Distance")
    )

    assert result.output_fxname == "Explosion"
    assert result.debug["metadata_candidates"] == ["5m"]
    assert "distance_excluded:5m" in result.issues
    assert result.quality == "needs_review"

    centimeters = _normalizer().normalize(
        "爆炸 10cm", PreferenceStore().get("No Distance")
    )
    assert centimeters.output_fxname == "Explosion"
    assert centimeters.debug["metadata_candidates"] == ["10cm"]


def test_issue_display_format_is_readable() -> None:
    assert FXNameEngineApp._display_issue("unknown_ascii:kuang") == "unknown_ascii: kuang"
    assert FXNameEngineApp._display_issue("distance_excluded:5m") == "distance_excluded: 5m"
    assert (
        FXNameEngineApp._display_issue("unsafe_fragment_rejected")
        == "unsafe_fragment_rejected"
    )


def test_token_review_status_labels_show_mapping_source() -> None:
    def token(source: str, status: str = "ok") -> FXToken:
        return FXToken("raw", "Text", "Text", "action", source, 1.0, status, [])

    assert FXNameEngineApp._review_status(token("canonical_csv")) == "mapped: canonical CSV"
    assert FXNameEngineApp._review_status(token("canonical_db")) == "mapped: glossary fallback"
    assert FXNameEngineApp._review_status(token("personal_map")) == (
        "mapped: personal dictionary"
    )
    assert FXNameEngineApp._review_status(token("preference_keep_raw", "needs_review")) == (
        "kept raw"
    )
    assert FXNameEngineApp._review_status(token("technical_metadata", "ignored")) == "ignored"
    assert FXNameEngineApp._review_status(token("ascii", "unknown")) == "unknown"


def test_manual_fxname_cases() -> None:
    store = PreferenceStore()
    normalizer = _normalizer()
    profile_names = {
        "default": "Default",
        "strict_review": "Strict Review",
        "keep_raw_friendly": "Keep Raw Friendly",
    }
    with MANUAL_CASES_CSV.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert reader.fieldnames == [
        "input",
        "expected_fxname",
        "expected_unknown",
        "allow_distance_in_fxname",
        "expected_metadata_candidate",
        "preset",
        "pollution_fragments",
        "note",
    ]
    assert len(rows) >= 150
    failures: list[str] = []
    for row_number, row in enumerate(rows, start=2):
        allow_distance = row["allow_distance_in_fxname"].lower() == "true"
        assert row["allow_distance_in_fxname"].lower() in {"true", "false"}
        profile = replace(
            store.get(profile_names[row["preset"]]),
            allow_distance_in_fxname=allow_distance,
        )
        result = normalizer.normalize(row["input"], profile)
        expected_unknown = _pipe_values(row["expected_unknown"])
        expected_metadata = _pipe_values(row["expected_metadata_candidate"])
        pollution_fragments = _pipe_values(row["pollution_fragments"])
        checks = {
            "fxname": (result.output_fxname, row["expected_fxname"]),
            "unknown": (result.unknowns, expected_unknown),
            "metadata": (result.debug["metadata_candidates"], expected_metadata),
            "nllb": (result.debug["nllb_fallback_used"], False),
        }
        for label, (actual, expected) in checks.items():
            if actual != expected:
                failures.append(
                    f"row {row_number} {row['input']!r} {label}: "
                    f"{actual!r} != {expected!r}"
                )
        output_lower = result.output_fxname.casefold()
        for fragment in pollution_fragments:
            if fragment.casefold() in output_lower:
                failures.append(
                    f"row {row_number} {row['input']!r} pollution leaked: {fragment!r}"
                )

    assert not failures, "\n" + "\n".join(failures)


def _pipe_values(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]
