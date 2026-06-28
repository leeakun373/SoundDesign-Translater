"""AI alias candidate imports stay review-only and never promote."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from fxengine.canonical_db import CANONICAL_COLUMNS, DEFAULT_CANONICAL_PATH, load_canonical_rows
from tools.import_ai_alias_candidates import import_ai_alias_candidates, main


def _write_prompt_pack(path: Path, items: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def _prompt_item(canonical: str, *, kind: str = "token", slot: str = "action") -> dict[str, object]:
    return {
        "canonical": canonical,
        "slot": slot,
        "candidate_type": kind,
        "record_count": 10,
        "examples": [],
        "instruction": "test",
    }


def _write_import_csv(
    path: Path,
    rows: list[dict[str, str]],
    *,
    fieldnames: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = fieldnames or list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _import_row(
    raw: str,
    canonical: str,
    *,
    slot: str = "action",
    pack: str = "new_candidate",
    **extra: str,
) -> dict[str, str]:
    return {
        "raw": raw,
        "canonical": canonical,
        "slot": slot,
        "source_note": f"reviewed_{pack};test",
        **extra,
    }


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    new_pack = tmp_path / "reviewed_new_candidate" / "alias_prompt_items.jsonl"
    alias_pack = tmp_path / "reviewed_alias_expansion" / "alias_prompt_items.jsonl"
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    return new_pack, alias_pack, canonical_path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_real_import_csv_cli_accepts_minimum_columns_and_does_not_mock_fill(
    tmp_path: Path,
) -> None:
    new_pack, alias_pack, canonical_path = _inputs(tmp_path)
    _write_prompt_pack(new_pack, [_prompt_item("Hit"), _prompt_item("Crack")])
    _write_prompt_pack(alias_pack, [_prompt_item("Gun", slot="object")])
    import_csv = tmp_path / "raw_ai_alias_output.csv"
    output_csv = tmp_path / "ai_alias_candidates_review_real.csv"
    report = tmp_path / "ai_alias_candidates_review_real_report.md"
    _write_import_csv(
        import_csv,
        [_import_row("重击声", "Hit", model="test-model")],
        fieldnames=["raw", "canonical", "slot", "source_note", "model"],
    )

    result = main(
        [
            "--new-candidate-pack",
            str(new_pack),
            "--alias-expansion-pack",
            str(alias_pack),
            "--canonical",
            str(canonical_path),
            "--import-csv",
            str(import_csv),
            "--output-csv",
            str(output_csv),
            "--report",
            str(report),
        ]
    )

    assert result == 0
    assert [(row["raw"], row["canonical"]) for row in _read_csv(output_csv)] == [
        ("重击声", "Hit")
    ]
    report_text = report.read_text(encoding="utf-8")
    assert "Real AI output review import only" in report_text
    assert "input_count: `1`" in report_text
    assert "output_count: `1`" in report_text


def test_keep_and_other_governance_fields_are_forced_to_review_constants(tmp_path: Path) -> None:
    new_pack, alias_pack, canonical_path = _inputs(tmp_path)
    _write_prompt_pack(new_pack, [_prompt_item("Hit")])
    _write_prompt_pack(alias_pack, [])
    import_csv = tmp_path / "import.csv"
    _write_import_csv(
        import_csv,
        [
            _import_row(
                "闷击声",
                "Hit",
                review_status="keep",
                source="runtime",
                priority="99",
                lang="en",
                rule_type="phrase",
            )
        ],
    )

    summary = import_ai_alias_candidates(
        new_pack,
        alias_pack,
        tmp_path / "out.csv",
        tmp_path / "report.md",
        canonical_path,
        import_csv=import_csv,
    )
    row = _read_csv(tmp_path / "out.csv")[0]

    assert row["review_status"] == "review"
    assert row["source"] == "ai_candidate"
    assert row["priority"] == "0"
    assert row["lang"] == "zh"
    assert row["rule_type"] == "alias"
    assert summary.has_keep is False


def test_existing_raw_is_skipped_globally(tmp_path: Path) -> None:
    new_pack, alias_pack, canonical_path = _inputs(tmp_path)
    _write_prompt_pack(new_pack, [_prompt_item("Hit")])
    _write_prompt_pack(alias_pack, [])
    existing_raw = load_canonical_rows(canonical_path)[0].raw
    import_csv = tmp_path / "import.csv"
    _write_import_csv(import_csv, [_import_row(existing_raw, "Hit")])

    summary = import_ai_alias_candidates(
        new_pack,
        alias_pack,
        tmp_path / "out.csv",
        tmp_path / "report.md",
        canonical_path,
        import_csv=import_csv,
    )

    assert _read_csv(tmp_path / "out.csv") == []
    assert summary.rejection_reason_counts == {"duplicate_existing_canonical_raw": 1}


def test_hit_crack_shot_and_english_duplicate_filters(tmp_path: Path) -> None:
    new_pack, alias_pack, canonical_path = _inputs(tmp_path)
    _write_prompt_pack(new_pack, [_prompt_item("Hit"), _prompt_item("Crack")])
    _write_prompt_pack(alias_pack, [_prompt_item("Shot")])
    import_csv = tmp_path / "import.csv"
    _write_import_csv(
        import_csv,
        [
            _import_row("命中", "Hit"),
            _import_row("Hit", "Hit"),
            _import_row("裂纹", "Crack"),
            _import_row("枪式麦克风", "Shot", pack="alias_expansion"),
            _import_row(
                "收音枪",
                "Shot",
                pack="alias_expansion",
                source_note="reviewed_alias_expansion;shotgun microphone context",
            ),
        ],
    )

    summary = import_ai_alias_candidates(
        new_pack,
        alias_pack,
        tmp_path / "out.csv",
        tmp_path / "report.md",
        canonical_path,
        import_csv=import_csv,
    )

    assert _read_csv(tmp_path / "out.csv") == []
    assert summary.rejection_reason_counts == {
        "forbidden_raw_命中": 1,
        "forbidden_raw_裂纹": 1,
        "forbidden_shot_microphone_context": 2,
        "raw_equals_canonical_english": 1,
    }


def test_gun_new_candidate_is_rejected_and_alias_expansion_is_kept(tmp_path: Path) -> None:
    new_pack, alias_pack, canonical_path = _inputs(tmp_path)
    _write_prompt_pack(new_pack, [_prompt_item("Gun", slot="object")])
    _write_prompt_pack(alias_pack, [_prompt_item("Gun", slot="object")])
    import_csv = tmp_path / "import.csv"
    _write_import_csv(
        import_csv,
        [
            _import_row("枪械新候选", "Gun", slot="object"),
            _import_row("枪械统称", "Gun", slot="object", pack="alias_expansion"),
        ],
    )

    summary = import_ai_alias_candidates(
        new_pack,
        alias_pack,
        tmp_path / "out.csv",
        tmp_path / "report.md",
        canonical_path,
        import_csv=import_csv,
    )
    rows = _read_csv(tmp_path / "out.csv")

    assert [row["raw"] for row in rows] == ["枪械统称"]
    assert "pack=alias_expansion" in rows[0]["note"]
    assert summary.rejection_reason_counts["gun_not_allowed_new_candidate"] == 1
    assert summary.gun_only_alias_expansion is True


def test_single_shot_stays_an_atomic_phrase(tmp_path: Path) -> None:
    new_pack, alias_pack, canonical_path = _inputs(tmp_path)
    _write_prompt_pack(new_pack, [_prompt_item("Single Shot", kind="phrase")])
    _write_prompt_pack(alias_pack, [])
    import_csv = tmp_path / "import.csv"
    _write_import_csv(
        import_csv,
        [
            _import_row("单次开火", "Single Shot"),
            _import_row("单次", "Single"),
        ],
    )

    summary = import_ai_alias_candidates(
        new_pack,
        alias_pack,
        tmp_path / "out.csv",
        tmp_path / "report.md",
        canonical_path,
        import_csv=import_csv,
    )
    rows = _read_csv(tmp_path / "out.csv")

    assert [(row["raw"], row["canonical"]) for row in rows] == [("单次开火", "Single Shot")]
    assert not any(row["canonical"] in {"Single", "Shot"} for row in rows)
    assert summary.rejection_reason_counts["candidate_not_in_reviewed_prompt_pack"] == 1


def test_output_schema_is_complete_and_deduplicated(tmp_path: Path) -> None:
    new_pack, alias_pack, canonical_path = _inputs(tmp_path)
    _write_prompt_pack(new_pack, [_prompt_item("Squeak")])
    _write_prompt_pack(alias_pack, [])
    import_csv = tmp_path / "import.csv"
    _write_import_csv(
        import_csv,
        [
            _import_row("挤压吱响", "Squeak"),
            _import_row("挤压吱响", "Squeak"),
            _import_row("金属吱响", "Squeak"),
        ],
    )

    summary = import_ai_alias_candidates(
        new_pack,
        alias_pack,
        tmp_path / "out.csv",
        tmp_path / "report.md",
        canonical_path,
        import_csv=import_csv,
    )
    with (tmp_path / "out.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        assert reader.fieldnames == list(CANONICAL_COLUMNS)

    assert len(rows) == 2
    assert all(row["review_status"] == "review" for row in rows)
    assert all(row["source"] == "ai_candidate" for row in rows)
    assert all(row["priority"] == "0" for row in rows)
    assert all(row["lang"] == "zh" for row in rows)
    assert all(row["rule_type"] == "alias" for row in rows)
    assert summary.input_count == 3
    assert summary.candidate_count == 2
    assert summary.rejected_count == 1


def test_canonical_tokens_hash_is_unchanged_by_real_import(tmp_path: Path) -> None:
    new_pack, alias_pack, canonical_path = _inputs(tmp_path)
    _write_prompt_pack(new_pack, [_prompt_item("Hit")])
    _write_prompt_pack(alias_pack, [])
    import_csv = tmp_path / "import.csv"
    _write_import_csv(import_csv, [_import_row("重物击打声", "Hit")])
    before = hashlib.sha256(canonical_path.read_bytes()).hexdigest().upper()

    summary = import_ai_alias_candidates(
        new_pack,
        alias_pack,
        tmp_path / "out.csv",
        tmp_path / "report.md",
        canonical_path,
        import_csv=import_csv,
    )

    assert hashlib.sha256(canonical_path.read_bytes()).hexdigest().upper() == before
    assert summary.canonical_tokens_sha256_before == before
    assert summary.canonical_tokens_sha256_after == before
    assert summary.canonical_tokens_changed is False
    assert summary.promote is False


def test_old_unreviewed_prompt_pack_path_is_rejected(tmp_path: Path) -> None:
    new_pack = tmp_path / "new_candidate" / "alias_prompt_items.jsonl"
    alias_pack = tmp_path / "reviewed_alias_expansion" / "alias_prompt_items.jsonl"
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    _write_prompt_pack(new_pack, [_prompt_item("Hit")])
    _write_prompt_pack(alias_pack, [])

    with pytest.raises(ValueError, match="Only the reviewed prompt pack is allowed"):
        import_ai_alias_candidates(
            new_pack,
            alias_pack,
            tmp_path / "out.csv",
            tmp_path / "report.md",
            canonical_path,
        )
