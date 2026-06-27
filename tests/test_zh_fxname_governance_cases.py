"""Regression baseline for zh FXName governance CSV cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.run_zh_fxname_cases import evaluate_csv, write_report

RESULTS_DIR = Path(__file__).resolve().parent / "results"
CASE_SETS = (
    (Path(__file__).resolve().parent / "zh_fxname_governance_cases_50.csv", 50, "zh_fxname_governance_report.json"),
    (Path(__file__).resolve().parent / "zh_fxname_governance_cases_150.csv", 150, "zh_fxname_governance_report_150.json"),
)


@pytest.mark.parametrize(("csv_path", "expected_total", "report_name"), CASE_SETS)
def test_zh_fxname_governance_cases_evaluate(
    csv_path: Path, expected_total: int, report_name: str
) -> None:
    report = evaluate_csv(csv_path)
    write_report(report, RESULTS_DIR / report_name)
    assert report.total == expected_total
    assert report.pass_count + report.fail_count + report.pending_count == report.total
    assert all(item.id for item in report.results)
