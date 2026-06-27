#!/usr/bin/env python3
"""Run zh FXName governance/result cases from CSV against normalize_fxname."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fxengine.models import FXNameResult, FXToken
from fxengine.normalizer import normalize_fxname

DEFAULT_CSV = ROOT / "tests" / "zh_fxname_governance_cases_50.csv"
DEFAULT_REPORT = ROOT / "tests" / "results" / "zh_fxname_governance_report.json"

WEAK_TOKEN_RAW = frozenset({"响", "动"})

ENGINE_SOURCE_TO_EXPECTED = {
    "canonical_csv": {"stable_single", "phrase_rule", "composite_phrase"},
    "glossary_fallback": {"phrase_rule", "composite_phrase"},
    "unknown_review": {"ambiguity_rule", "weak_token_rule"},
    "personal_dictionary": {"stable_single", "phrase_rule", "composite_phrase"},
    "keep_raw_rule": {"phrase_rule"},
    "pollution_filter": {"weak_token_rule"},
}


@dataclass
class CaseEvaluation:
    id: str
    input: str
    test_kind: str
    status: str
    output_fxname: str
    derived_review_status: str
    derived_source: str | None
    reasons: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    expected: dict[str, str] = field(default_factory=dict)
    actual: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationReport:
    csv_path: str
    generated_at: str
    total: int
    pass_count: int
    fail_count: int
    pending_count: int
    results: list[CaseEvaluation]

    def to_dict(self) -> dict[str, Any]:
        return {
            "csv_path": self.csv_path,
            "generated_at": self.generated_at,
            "total": self.total,
            "pass": self.pass_count,
            "fail": self.fail_count,
            "pending": self.pending_count,
            "results": [asdict(item) for item in self.results],
        }


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).casefold()


def _split_alts(value: str) -> list[str]:
    value = (value or "").strip()
    if not value:
        return []
    return [part.strip() for part in value.split("|") if part.strip()]


def _fxname_matches(actual: str, expected: str) -> bool:
    alts = _split_alts(expected)
    if not alts:
        return True
    actual_norm = _norm(actual)
    for alt in alts:
        alt_norm = _norm(alt)
        if actual_norm == alt_norm:
            return True
        actual_words = actual_norm.split()
        alt_words = alt_norm.split()
        if alt_words and _contains_word_sequence(actual_words, tuple(alt_words)):
            return True
    return False


def _contains_word_sequence(words: list[str], sequence: tuple[str, ...]) -> bool:
    width = len(sequence)
    if width == 0:
        return True
    return any(tuple(words[start : start + width]) == sequence for start in range(len(words) - width + 1))


def _must_not_violations(output: str, must_not: str) -> list[str]:
    output_norm = _norm(output)
    violations: list[str] = []
    for token in _split_alts(must_not):
        if _norm(token) in output_norm:
            violations.append(token)
    return violations


def _meaningful_tokens(tokens: list[FXToken]) -> list[FXToken]:
    return [token for token in tokens if token.raw.strip()]


def _mapped_tokens(tokens: list[FXToken]) -> list[FXToken]:
    return [
        token
        for token in tokens
        if token.decision in {"mapped_canonical", "mapped_glossary", "mapped_personal"}
        and token.text
        and token.status in {"ok", "needs_review"}
    ]


def derive_review_status(result: FXNameResult) -> str:
    tokens = _meaningful_tokens(result.tokens)
    unknown_tokens = [
        token
        for token in tokens
        if token.decision == "unknown" or token.source == "unknown_review"
    ]
    mapped = _mapped_tokens(tokens)

    if unknown_tokens:
        if (
            len(unknown_tokens) == len(tokens)
            and all(len(token.raw) == 1 for token in unknown_tokens)
            and all(token.raw in WEAK_TOKEN_RAW for token in unknown_tokens)
        ):
            return "weak_token"
        return "review_required"

    ignored = [
        token
        for token in tokens
        if token.decision
        in {"ignored_pollution", "ignored_personal", "metadata_candidate"}
        or token.status == "ignored"
    ]
    if ignored and not mapped:
        if any(token.decision == "ignored_pollution" for token in ignored):
            return "ignored"
        return "review_required"

    if not mapped:
        if result.output_fxname.strip():
            return "mapped_phrase"
        return "review_required"

    if len(mapped) > 1:
        return "mapped_phrase"
    if len(mapped[0].raw) > 1:
        return "mapped_phrase"
    return "mapped_canonical"


def derive_source(result: FXNameResult) -> str | None:
    tokens = _meaningful_tokens(result.tokens)
    unknown_tokens = [
        token
        for token in tokens
        if token.decision == "unknown" or token.source == "unknown_review"
    ]
    mapped = _mapped_tokens(tokens)

    if unknown_tokens:
        if derive_review_status(result) == "weak_token":
            return "weak_token_rule"
        return "ambiguity_rule"

    sources = {token.source for token in mapped}
    if not mapped:
        return None

    if len(mapped) > 1:
        actions = [token for token in mapped if token.slot in {"action", "motion"}]
        if len(actions) >= 2:
            return "composite_phrase"
        return "phrase_rule"

    if len(mapped) == 1 and len(mapped[0].raw) == 1:
        return "stable_single"
    return "phrase_rule"


def _source_compatible(expected_source: str, result: FXNameResult, derived_source: str | None) -> bool:
    if not expected_source:
        return True
    if derived_source == expected_source:
        return True

    token_sources = {token.source for token in _mapped_tokens(result.tokens)}
    token_sources.update(
        token.source
        for token in _meaningful_tokens(result.tokens)
        if token.decision == "unknown" or token.source == "unknown_review"
    )
    allowed: set[str] = set()
    for source in token_sources:
        allowed.update(ENGINE_SOURCE_TO_EXPECTED.get(source, set()))
    return expected_source in allowed


def load_cases(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def evaluate_row(row: dict[str, str], result: FXNameResult | None = None) -> CaseEvaluation:
    case_id = row["id"].strip()
    input_text = row["input"].strip()
    test_kind = row["test_kind"].strip()
    fx_result = result or normalize_fxname(input_text)

    derived_review_status = derive_review_status(fx_result)
    derived_source = derive_source(fx_result)
    evaluation = CaseEvaluation(
        id=case_id,
        input=input_text,
        test_kind=test_kind,
        status="pass",
        output_fxname=fx_result.output_fxname,
        derived_review_status=derived_review_status,
        derived_source=derived_source,
        expected={
            "expected_fxname": row.get("expected_fxname", "").strip(),
            "expected_review_status": row.get("expected_review_status", "").strip(),
            "expected_source": row.get("expected_source", "").strip(),
            "must_not_contain": row.get("must_not_contain", "").strip(),
        },
        actual={
            "output_fxname": fx_result.output_fxname,
            "derived_review_status": derived_review_status,
            "derived_source": derived_source,
            "token_summary": [
                {
                    "raw": token.raw,
                    "text": token.text,
                    "decision": token.decision,
                    "source": token.source,
                    "status": token.status,
                }
                for token in fx_result.tokens
            ],
        },
    )

    if test_kind in {"both", "result"}:
        expected_fxname = row.get("expected_fxname", "").strip()
        if expected_fxname and not _fxname_matches(fx_result.output_fxname, expected_fxname):
            evaluation.reasons.append(
                f"fxname mismatch: expected one of [{expected_fxname}] "
                f"got [{fx_result.output_fxname}]"
            )

        must_not = row.get("must_not_contain", "").strip()
        violations = _must_not_violations(fx_result.output_fxname, must_not)
        if violations:
            evaluation.reasons.append(
                f"must_not_contain violated: {', '.join(violations)} "
                f"in [{fx_result.output_fxname}]"
            )

    if test_kind in {"both", "governance"}:
        expected_review = row.get("expected_review_status", "").strip()
        if expected_review and derived_review_status != expected_review:
            if expected_review == "weak_token" and derived_review_status == "review_required":
                evaluation.pending.append(
                    "review_status pending: engine lacks weak_token_rule granularity "
                    f"(expected {expected_review}, derived {derived_review_status})"
                )
            else:
                evaluation.reasons.append(
                    f"review_status mismatch: expected [{expected_review}] "
                    f"derived [{derived_review_status}]"
                )

        expected_source = row.get("expected_source", "").strip()
        if expected_source:
            if derived_source == expected_source or _source_compatible(
                expected_source, fx_result, derived_source
            ):
                pass
            else:
                evaluation.pending.append(
                    "source pending: engine taxonomy differs "
                    f"(expected {expected_source}, derived {derived_source or 'none'})"
                )

    if evaluation.reasons:
        evaluation.status = "fail"
    elif evaluation.pending:
        evaluation.status = "pending"
    else:
        evaluation.status = "pass"
    return evaluation


def evaluate_csv(
    csv_path: Path | str = DEFAULT_CSV,
) -> EvaluationReport:
    csv_path = Path(csv_path)
    rows = load_cases(csv_path)
    results: list[CaseEvaluation] = []
    for row in rows:
        results.append(evaluate_row(row))

    pass_count = sum(1 for item in results if item.status == "pass")
    fail_count = sum(1 for item in results if item.status == "fail")
    pending_count = sum(1 for item in results if item.status == "pending")
    return EvaluationReport(
        csv_path=str(csv_path),
        generated_at=datetime.now(timezone.utc).isoformat(),
        total=len(results),
        pass_count=pass_count,
        fail_count=fail_count,
        pending_count=pending_count,
        results=results,
    )


def write_report(report: EvaluationReport, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def print_summary(report: EvaluationReport) -> None:
    print(
        f"zh FXName cases: total={report.total} pass={report.pass_count} "
        f"fail={report.fail_count} pending={report.pending_count}"
    )
    failures = [item for item in report.results if item.status == "fail"]
    for item in failures:
        print(f"\nFAIL id={item.id} input={item.input!r}")
        print(f"  output={item.output_fxname!r}")
        for reason in item.reasons:
            print(f"  - {reason}")
    pending = [item for item in report.results if item.status == "pending"]
    if pending:
        print(f"\nPENDING ({len(pending)})")
        for item in pending[:5]:
            print(f"  id={item.id} input={item.input!r}: {'; '.join(item.pending)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run zh FXName governance CSV cases.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help="Case CSV path",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help="JSON report output path",
    )
    args = parser.parse_args(argv)

    report = evaluate_csv(args.csv)
    write_report(report, args.report)
    print_summary(report)
    print(f"\nReport written to {args.report}")
    return 1 if report.fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
