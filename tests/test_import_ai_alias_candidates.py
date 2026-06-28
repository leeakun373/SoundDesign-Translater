"""AI alias candidate import stays review-only and never promotes."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from fxengine.canonical_db import CANONICAL_COLUMNS, DEFAULT_CANONICAL_PATH
from tools.import_ai_alias_candidates import import_ai_alias_candidates


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


def _write_import_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANONICAL_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _import_row(
    raw: str,
    canonical: str,
    *,
    slot: str = "action",
    pack: str = "new_candidate",
    review_status: str = "review",
    source: str = "ai_candidate",
    priority: str = "0",
) -> dict[str, str]:
    return {
        "raw": raw,
        "canonical": canonical,
        "slot": slot,
        "lang": "zh",
        "priority": priority,
        "rule_type": "phrase",
        "review_status": review_status,
        "ambiguity": "high",
        "tags": "test",
        "source": source,
        "note": f"import_test;pack={pack}",
    }


def test_dry_run_generates_review_only_candidates(tmp_path: Path) -> None:
    new_pack = tmp_path / "reviewed_new_candidate" / "alias_prompt_items.jsonl"
    alias_pack = tmp_path / "reviewed_alias_expansion" / "alias_prompt_items.jsonl"
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())

    _write_prompt_pack(
        new_pack,
        [
            _prompt_item("Hit"),
            _prompt_item("Single Shot", kind="phrase"),
        ],
    )
    _write_prompt_pack(alias_pack, [_prompt_item("Gun", slot="object")])

    summary = import_ai_alias_candidates(
        new_pack,
        alias_pack,
        tmp_path / "out.csv",
        tmp_path / "report.md",
        canonical_path,
    )
    rows = list(csv.DictReader((tmp_path / "out.csv").open(encoding="utf-8")))

    assert summary.candidate_count == len(rows)
    assert summary.candidate_count > 0
    assert summary.has_keep is False
    assert summary.all_source_ai_candidate is True
    assert summary.all_priority_zero is True
    assert summary.promote is False
    assert summary.ai_invoked is False
    assert all(row["review_status"] == "review" for row in rows)
    assert all(row["source"] == "ai_candidate" for row in rows)
    assert all(row["priority"] == "0" for row in rows)


def test_gun_only_appears_from_alias_expansion(tmp_path: Path) -> None:
    new_pack = tmp_path / "reviewed_new_candidate" / "alias_prompt_items.jsonl"
    alias_pack = tmp_path / "reviewed_alias_expansion" / "alias_prompt_items.jsonl"
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())

    _write_prompt_pack(new_pack, [_prompt_item("Hit")])
    _write_prompt_pack(alias_pack, [_prompt_item("Gun", slot="object")])

    import_ai_alias_candidates(
        new_pack,
        alias_pack,
        tmp_path / "out.csv",
        tmp_path / "report.md",
        canonical_path,
    )
    rows = list(csv.DictReader((tmp_path / "out.csv").open(encoding="utf-8")))
    gun_rows = [row for row in rows if row["canonical"] == "Gun"]

    assert gun_rows
    assert all("pack=alias_expansion" in row["note"] for row in gun_rows)
    assert not any(row["canonical"] == "Gun" and "pack=new_candidate" in row["note"] for row in rows)


def test_import_csv_rejects_keep_block_and_forbidden_aliases(tmp_path: Path) -> None:
    new_pack = tmp_path / "reviewed_new_candidate" / "alias_prompt_items.jsonl"
    alias_pack = tmp_path / "reviewed_alias_expansion" / "alias_prompt_items.jsonl"
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    import_csv = tmp_path / "import.csv"

    _write_prompt_pack(new_pack, [_prompt_item("Hit"), _prompt_item("Crack"), _prompt_item("Shot")])
    _write_prompt_pack(alias_pack, [])
    _write_import_csv(
        import_csv,
        [
            _import_row("打击", "Hit"),
            _import_row("命中", "Hit"),
            _import_row("裂纹", "Crack"),
            _import_row("霰弹麦", "Shot", pack="new_candidate"),
            _import_row("keep-me", "Hit", review_status="keep"),
            _import_row("manual", "Hit", source="manual"),
            _import_row("prio", "Hit", priority="10"),
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
    rows = list(csv.DictReader((tmp_path / "out.csv").open(encoding="utf-8")))

    assert [row["raw"] for row in rows if row["canonical"] == "Hit"] == ["打击"]
    assert summary.rejection_reason_counts["forbidden_raw_命中"] >= 1
    assert summary.rejection_reason_counts["forbidden_raw_裂纹"] >= 1
    assert summary.rejection_reason_counts["forbidden_shot_microphone_context"] >= 1
    assert summary.rejection_reason_counts["review_status_keep_forbidden"] >= 1
    assert summary.rejection_reason_counts["source_not_ai_candidate"] >= 1
    assert summary.rejection_reason_counts["priority_not_zero"] >= 1


def test_import_deduplicates_raw_canonical_slot_and_existing_canonical(tmp_path: Path) -> None:
    new_pack = tmp_path / "reviewed_new_candidate" / "alias_prompt_items.jsonl"
    alias_pack = tmp_path / "reviewed_alias_expansion" / "alias_prompt_items.jsonl"
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    import_csv = tmp_path / "import.csv"

    _write_prompt_pack(new_pack, [_prompt_item("Impact")])
    _write_prompt_pack(alias_pack, [])
    _write_import_csv(
        import_csv,
        [
            _import_row("撞击", "Impact"),
            _import_row("撞击", "Impact"),
            _import_row("冲击", "Impact"),
            _import_row("碰击", "Impact"),
            _import_row("新 alias", "Impact"),
        ],
    )

    import_ai_alias_candidates(
        new_pack,
        alias_pack,
        tmp_path / "out.csv",
        tmp_path / "report.md",
        canonical_path,
        import_csv=import_csv,
    )
    rows = list(csv.DictReader((tmp_path / "out.csv").open(encoding="utf-8")))
    raws = [row["raw"] for row in rows if row["canonical"] == "Impact"]

    assert "撞击" not in raws
    assert len(raws) == len(set(raws))
    assert len(rows) <= 5


def test_single_shot_keeps_phrase_canonical(tmp_path: Path) -> None:
    new_pack = tmp_path / "reviewed_new_candidate" / "alias_prompt_items.jsonl"
    alias_pack = tmp_path / "reviewed_alias_expansion" / "alias_prompt_items.jsonl"
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    import_csv = tmp_path / "import.csv"

    _write_prompt_pack(new_pack, [_prompt_item("Single Shot", kind="phrase")])
    _write_prompt_pack(alias_pack, [])
    _write_import_csv(
        import_csv,
        [
            _import_row("单发", "Single Shot"),
            _import_row("单发", "Single"),
        ],
    )

    import_ai_alias_candidates(
        new_pack,
        alias_pack,
        tmp_path / "out.csv",
        tmp_path / "report.md",
        canonical_path,
        import_csv=import_csv,
    )
    rows = list(csv.DictReader((tmp_path / "out.csv").open(encoding="utf-8")))

    assert all(row["canonical"] == "Single Shot" for row in rows)
    assert not any(row["canonical"] in {"Single", "Shot"} for row in rows)


def test_canonical_tokens_hash_unchanged(tmp_path: Path) -> None:
    new_pack = tmp_path / "reviewed_new_candidate" / "alias_prompt_items.jsonl"
    alias_pack = tmp_path / "reviewed_alias_expansion" / "alias_prompt_items.jsonl"
    canonical_path = tmp_path / "canonical_tokens.csv"
    canonical_path.write_bytes(DEFAULT_CANONICAL_PATH.read_bytes())
    before = hashlib.sha256(canonical_path.read_bytes()).hexdigest().upper()

    _write_prompt_pack(new_pack, [_prompt_item("Hit")])
    _write_prompt_pack(alias_pack, [])

    summary = import_ai_alias_candidates(
        new_pack,
        alias_pack,
        tmp_path / "out.csv",
        tmp_path / "report.md",
        canonical_path,
    )

    after = hashlib.sha256(canonical_path.read_bytes()).hexdigest().upper()
    assert before == after
    assert summary.canonical_tokens_changed is False


def test_production_dry_run_import() -> None:
    summary = import_ai_alias_candidates()
    csv_path = Path(summary.csv_path)
    report_path = Path(summary.report_path)

    assert csv_path.is_file()
    assert report_path.is_file()
    assert summary.candidate_count > 0
    assert summary.has_keep is False
    assert summary.gun_only_alias_expansion is True

    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    new_candidate_guns = [
        row
        for row in rows
        if row["canonical"] == "Gun" and "pack=new_candidate" in row["note"]
    ]
    assert new_candidate_guns == []
