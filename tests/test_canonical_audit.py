"""Read-only canonical CSV audit coverage."""

from __future__ import annotations

import json
from pathlib import Path

from fxengine.canonical_audit import audit_canonical_csv, main
from fxengine.canonical_db import DEFAULT_CANONICAL_PATH


def test_current_canonical_csv_passes_audit() -> None:
    result = audit_canonical_csv()

    assert result.passed is True
    assert result.total_rows == 358
    assert result.runtime_keep_rows == 350
    assert result.review_rows == 8
    assert result.reject_rows == 0
    assert result.valid_rows == 358
    assert result.error_count == 0
    assert result.warning_count == 3
    assert result.issue_counts == {"high_risk_single_keep": 3}
    assert result.conflict_count == 0
    assert len(result.high_risk_single_results) == 20
    assert result.path == str(DEFAULT_CANONICAL_PATH)


def test_audit_reports_all_required_quality_failures(tmp_path: Path) -> None:
    path = tmp_path / "bad_canonical.csv"
    path.write_text(
        "raw,canonical,slot,lang,priority,rule_type,review_status,ambiguity,tags,source,note\n"
        "撞,Impact,action,zh,100,phrase,keep,low,impact,manual,\n"
        "撞,Impact,action,zh,100,phrase,keep,low,impact,manual,\n"
        "撞,Hit,motion,zh,101,bad_rule,keep,low,bad tag,manual,\n"
        ",,,,,,keep,,a//b,,\n"
        "测试,Test,illegal,xx,-1,phrase,bad,illegal,UPPER,bad,\n",
        encoding="utf-8",
    )

    result = audit_canonical_csv(path)
    codes = {issue.code for issue in result.issues}

    assert result.passed is False
    assert result.issue_count == len(result.issues)
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
        "invalid_rule_type",
        "invalid_review_status",
        "invalid_ambiguity",
        "invalid_source",
        "invalid_tags",
        "duplicate_row",
    } <= codes
    assert result.valid_rows < result.total_rows


def test_audit_cli_emits_structured_json(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "missing.csv"

    exit_code = main([str(missing), "--no-write"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["passed"] is False
    assert payload["issue_count"] == 1
    assert payload["issue_counts"] == {"file_not_found": 1}
