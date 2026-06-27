"""Read-only canonical CSV audit coverage."""

from __future__ import annotations

import json
from pathlib import Path

from fxengine.canonical_audit import audit_canonical_csv, main
from fxengine.canonical_db import DEFAULT_CANONICAL_PATH


def test_current_canonical_csv_passes_audit() -> None:
    result = audit_canonical_csv()

    assert result.passed is True
    assert result.total_rows == 248
    assert result.valid_rows == 248
    assert result.issue_counts == {}
    assert result.path == str(DEFAULT_CANONICAL_PATH)


def test_audit_reports_all_required_quality_failures(tmp_path: Path) -> None:
    path = tmp_path / "bad_canonical.csv"
    path.write_text(
        "raw,canonical,slot,lang,priority,tags,note\n"
        "撞,Impact,action,zh,100,impact,\n"
        "撞,Impact,action,zh,100,impact,\n"
        "撞,Hit,motion,zh,101,bad tag,\n"
        ",,,,,a//b,\n"
        "测试,Test,illegal,xx,-1,UPPER,\n",
        encoding="utf-8",
    )

    result = audit_canonical_csv(path)
    codes = {issue.code for issue in result.issues}

    assert result.passed is False
    assert {
        "duplicate_raw",
        "conflicting_canonical",
        "conflicting_slot",
        "empty_raw",
        "empty_canonical",
        "empty_slot",
        "invalid_priority",
        "invalid_lang",
        "invalid_slot",
        "invalid_tags",
        "duplicate_row",
    } <= codes
    assert result.valid_rows < result.total_rows


def test_audit_cli_emits_structured_json(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "missing.csv"

    exit_code = main([str(missing)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["passed"] is False
    assert payload["issue_counts"] == {"file_not_found": 1}
