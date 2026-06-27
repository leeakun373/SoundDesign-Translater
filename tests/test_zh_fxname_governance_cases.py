"""Regression baseline for zh FXName governance CSV cases."""

from __future__ import annotations

from pathlib import Path

from tools.run_zh_fxname_cases import DEFAULT_CSV, evaluate_csv, write_report

RESULTS_DIR = Path(__file__).resolve().parent / "results"
REPORT_PATH = RESULTS_DIR / "zh_fxname_governance_report.json"


def test_zh_fxname_governance_cases_evaluate() -> None:
    report = evaluate_csv(DEFAULT_CSV)
    write_report(report, REPORT_PATH)
    assert report.total == 50
    assert report.pass_count + report.fail_count + report.pending_count == report.total
    assert all(item.id for item in report.results)
