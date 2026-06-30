"""translator 轨道 A 探针回归：R13–R45 固化 CSV。

断言：无 unknown / NLLB token，输出与 expected_fxname 一致。
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from translator import api

CSV_PATH = Path(__file__).resolve().parent / "zh_fxname_probe_regression.csv"


def _load_rows() -> list[dict[str, str]]:
    with CSV_PATH.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _trace_issues(traces) -> tuple[list[str], list[str]]:
    unknowns: list[str] = []
    nllb: list[str] = []
    for t in traces:
        if t.kind != "zh" or t.decision == "dropped_stop":
            continue
        base = (t.decision or "").split("+", 1)[0]
        if base == "unknown" or not t.translated:
            unknowns.append(t.source_text)
        elif base == "nllb":
            nllb.append(t.source_text)
    return unknowns, nllb


@pytest.fixture(scope="module")
def regression_rows() -> list[dict[str, str]]:
    rows = _load_rows()
    assert len(rows) >= 1400, f"probe regression CSV too small: {len(rows)}"
    return rows


def test_probe_regression_csv_row_count(regression_rows: list[dict[str, str]]) -> None:
    assert len(regression_rows) == 1482


@pytest.mark.parametrize("row", _load_rows(), ids=lambda r: r["id"])
def test_probe_regression_row(row: dict[str, str]) -> None:
    text = row["input"]
    expected = row["expected_fxname"]
    res = api.to_fxname(text)
    unknowns, nllb = _trace_issues(res.detail.traces)

    if row.get("must_not_unknown", "yes") == "yes":
        assert not unknowns, f"{row['id']} {text!r} unknown tokens: {unknowns}"
    if row.get("must_not_nllb", "yes") == "yes":
        assert not nllb, f"{row['id']} {text!r} nllb tokens: {nllb}"

    assert res.text == expected, (
        f"{row['id']} round={row['round']} theme={row['theme']}\n"
        f"  input:    {text!r}\n"
        f"  expected: {expected!r}\n"
        f"  actual:   {res.text!r}"
    )
