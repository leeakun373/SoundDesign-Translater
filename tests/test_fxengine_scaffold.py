"""FXName Engine v0.3 architecture and behavior tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fxengine.example_retrieval import ExampleRetriever
from fxengine.metadata_writer import MetadataWriter
from fxengine.normalizer import FXNameNormalizer
from fxengine.personal_dictionary import PersonalDictionary
from fxengine.polish import FXNamePolisher
from fxengine.preferences import FXPreferences, PreferenceStore
from fxengine.scorer import BoomScorer
from fxengine.suggest import FXNameSuggester
from glossary.boom_style import BoomStyleIndex


ROOT = Path(__file__).resolve().parents[1]


def _normalizer(
    *,
    dictionary: PersonalDictionary | None = None,
    preferences: FXPreferences | None = None,
    scorer: BoomScorer | None = None,
) -> FXNameNormalizer:
    return FXNameNormalizer(
        personal_dictionary=dictionary,
        preferences=preferences,
        scorer=scorer or BoomScorer(BoomStyleIndex(ROOT / "tests" / "__missing_fxengine_boom.sqlite")),
    )


def test_required_normalize_examples() -> None:
    normalizer = _normalizer()

    assert normalizer.normalize("金属 门 撞击").output_fxname == "Metal Door Impact"
    assert normalizer.normalize("木门滑开").output_fxname == "Wood Door Slide Open"
    assert normalizer.normalize("door 推开 wood").output_fxname == "Door Push Open Wood"
    assert (
        normalizer.normalize("火箭 发射 爆炸 long tail 5m").output_fxname
        == "Rocket Launch Explosion Long Tail 5m"
    )


def test_unknown_ascii_requires_review() -> None:
    result = _normalizer().normalize("kuang")

    assert result.output_fxname == ""
    assert result.quality == "needs_review"
    assert result.unknowns == ["kuang"]
    assert "unknown_ascii:kuang" in result.issues
    assert result.debug["nllb_fallback_used"] is False


def test_personal_dictionary_alias_persists(tmp_path: Path) -> None:
    path = tmp_path / "personal_dictionary.json"
    dictionary = PersonalDictionary(path)
    before = _normalizer(dictionary=dictionary).normalize("kuang")
    assert before.quality == "needs_review"

    dictionary.add_alias("kuang", "Metal Impact")
    reloaded = PersonalDictionary(path)
    after = _normalizer(dictionary=reloaded).normalize("kuang")

    assert after.output_fxname == "Metal Impact"
    assert after.quality == "pass"
    assert after.tokens[0].source == "personal_dictionary"
    assert after.tokens[0].decision == "mapped_personal"


def test_distance_preference_controls_fxname_and_metadata_candidate() -> None:
    allow = FXPreferences(allow_distance_in_fxname=True)
    deny = FXPreferences(allow_distance_in_fxname=False)

    allowed = _normalizer(preferences=allow).normalize("爆炸 5m")
    denied = _normalizer(preferences=deny).normalize("爆炸 5m")

    assert allowed.output_fxname == "Explosion 5m"
    assert denied.output_fxname == "Explosion"
    assert denied.debug["metadata_candidates"] == ["5m"]
    assert any(token.raw == "5m" and token.status == "ignored" for token in denied.tokens)


def test_preference_store_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "preferences.json"
    store = PreferenceStore(path)
    store.set(
        FXPreferences(
            name="No Distance",
            preserve_order=True,
            allow_distance_in_fxname=False,
            boom_can_reorder=False,
            boom_suggestion_only=True,
        )
    )

    reloaded = PreferenceStore(path)
    assert reloaded.get("No Distance").allow_distance_in_fxname is False
    assert "No Distance" in reloaded.names()


def test_boom_suggestion_never_overwrites_final(tmp_path: Path) -> None:
    db_path = tmp_path / "boom.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE tokens (
                token TEXT PRIMARY KEY,
                freq INTEGER NOT NULL,
                filename_freq INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE phrases (
                phrase TEXT PRIMARY KEY,
                n INTEGER NOT NULL,
                freq INTEGER NOT NULL,
                filename_freq INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        conn.executemany(
            "INSERT INTO tokens(token, freq, filename_freq) VALUES (?, ?, ?)",
            [("howl", 10, 5), ("wolf", 10, 5), ("rocket", 5, 2)],
        )
        conn.execute(
            "INSERT INTO phrases(phrase, n, freq, filename_freq) VALUES ('wolf howl', 2, 100, 80)"
        )

    scorer = BoomScorer(BoomStyleIndex(db_path))
    result = _normalizer(scorer=scorer).normalize("howl wolf rocket")

    assert result.output_fxname == "Howl Wolf Rocket"
    assert result.boom_suggestion == "Wolf Howl Rocket"
    assert result.suggestions == ["Wolf Howl Rocket"]


def test_structured_stubs_do_not_crash() -> None:
    normalized = _normalizer().normalize("金属 门 撞击")
    metadata = MetadataWriter().write(normalized.input_text, normalized.tokens)
    examples = ExampleRetriever().retrieve(normalized.output_fxname)
    polish = FXNamePolisher().polish("metal door was hit")
    suggestions = FXNameSuggester().suggest("重金属门撞击")

    assert metadata.quality == "needs_review" and metadata.debug["stub"] is True
    assert metadata.issues == ["stub"]
    assert examples.quality == "needs_review" and examples.examples == []
    assert polish.quality == "needs_review" and polish.output_fxname == ""
    assert suggestions.quality == "needs_review" and suggestions.candidates == []
