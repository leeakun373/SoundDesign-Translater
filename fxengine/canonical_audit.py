"""Read-only quality audit and report writer for canonical token CSV files."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

from fxengine.canonical_db import (
    ALLOWED_AMBIGUITY,
    ALLOWED_LANGS,
    ALLOWED_REVIEW_STATUSES,
    ALLOWED_RULE_TYPES,
    ALLOWED_SLOTS,
    ALLOWED_SOURCES,
    CANONICAL_COLUMNS,
    DEFAULT_CANONICAL_PATH,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = ROOT / "reports" / "canonical_token_audit.md"
DEFAULT_CONFLICT_PATH = ROOT / "fxengine" / "data" / "canonical_token_conflicts.csv"
CONFLICT_COLUMNS = (
    "raw",
    "row_numbers",
    "canonical_values",
    "slot_values",
    "issue_codes",
    "severity",
    "note",
)
HIGH_RISK_SINGLE_CHARS = (
    "打",
    "击",
    "碰",
    "响",
    "动",
    "甩",
    "敲",
    "蹭",
    "划",
    "摔",
    "晃",
    "震",
    "抖",
    "滚",
    "转",
    "开",
    "关",
    "破",
    "裂",
    "碎",
)
TAG_RE = re.compile(r"^[a-z0-9_-]+(?:/[a-z0-9_-]+)*$")


@dataclass(frozen=True)
class CanonicalAuditIssue:
    code: str
    message: str
    severity: str = "error"
    row_numbers: list[int] = field(default_factory=list)
    raw: str = ""
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalConflict:
    raw: str
    row_numbers: list[int]
    canonical_values: list[str]
    slot_values: list[str]
    issue_codes: list[str]
    severity: str = "error"
    note: str = ""

    def to_csv_row(self) -> dict[str, str]:
        return {
            "raw": self.raw,
            "row_numbers": "|".join(str(value) for value in self.row_numbers),
            "canonical_values": "|".join(self.canonical_values),
            "slot_values": "|".join(self.slot_values),
            "issue_codes": "|".join(self.issue_codes),
            "severity": self.severity,
            "note": self.note,
        }


@dataclass(frozen=True)
class CanonicalAuditResult:
    path: str
    total_rows: int
    valid_rows: int
    runtime_keep_rows: int
    review_rows: int
    reject_rows: int
    issues: list[CanonicalAuditIssue]
    high_risk_single_results: list[dict[str, object]] = field(default_factory=list)
    conflicts: list[CanonicalConflict] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.error_count == 0

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def error_count(self) -> int:
        return sum(issue.severity == "error" for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == "warning" for issue in self.issues)

    @property
    def issue_counts(self) -> dict[str, int]:
        return dict(Counter(issue.code for issue in self.issues))

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "passed": self.passed,
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "runtime_keep_rows": self.runtime_keep_rows,
            "review_rows": self.review_rows,
            "reject_rows": self.reject_rows,
            "issue_count": self.issue_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issue_counts": self.issue_counts,
            "high_risk_single_results": self.high_risk_single_results,
            "conflict_count": self.conflict_count,
            "conflicts": [asdict(conflict) for conflict in self.conflicts],
            "issues": [asdict(issue) for issue in self.issues],
        }


def audit_canonical_csv(path: Path = DEFAULT_CANONICAL_PATH) -> CanonicalAuditResult:
    """Inspect CSV quality without changing the source file."""
    path = Path(path)
    if not path.is_file():
        issue = CanonicalAuditIssue(
            code="file_not_found",
            message=f"Canonical token CSV not found: {path}",
        )
        return CanonicalAuditResult(str(path), 0, 0, 0, 0, 0, [issue])

    issues: list[CanonicalAuditIssue] = []
    rows: list[tuple[int, dict[str, str]]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing_columns = [
            column for column in CANONICAL_COLUMNS if column not in fieldnames
        ]
        if missing_columns:
            issues.append(
                CanonicalAuditIssue(
                    code="missing_column",
                    message="Canonical CSV is missing required columns",
                    details={"columns": missing_columns},
                )
            )
        for row_number, source_row in enumerate(reader, start=2):
            row = {
                column: (source_row.get(column) or "").strip()
                for column in CANONICAL_COLUMNS
            }
            rows.append((row_number, row))
            _audit_row(row_number, row, issues)

    conflicts = _audit_duplicates(rows, issues)
    high_risk_results = _audit_high_risk(rows, issues)
    issues.sort(
        key=lambda issue: (
            issue.row_numbers[:1] or [0],
            issue.severity,
            issue.code,
            issue.raw,
        )
    )
    error_rows = {
        row_number
        for issue in issues
        if issue.severity == "error"
        for row_number in issue.row_numbers
    }
    statuses = Counter(row["review_status"] for _number, row in rows)
    return CanonicalAuditResult(
        path=str(path),
        total_rows=len(rows),
        valid_rows=max(0, len(rows) - len(error_rows)),
        runtime_keep_rows=statuses["keep"],
        review_rows=statuses["review"],
        reject_rows=statuses["reject"],
        issues=issues,
        high_risk_single_results=high_risk_results,
        conflicts=conflicts,
    )


def _audit_row(
    row_number: int,
    row: dict[str, str],
    issues: list[CanonicalAuditIssue],
) -> None:
    raw = row["raw"]
    for column in ("raw", "slot", "lang", "priority", "rule_type", "review_status", "ambiguity"):
        if not row[column]:
            issues.append(
                CanonicalAuditIssue(
                    code=f"empty_{column}",
                    message=f"{column} must not be empty",
                    row_numbers=[row_number],
                    raw=raw,
                )
            )

    review_status = row["review_status"]
    if review_status not in ALLOWED_REVIEW_STATUSES:
        _invalid_set_issue(
            issues,
            row_number,
            raw,
            "review_status",
            review_status,
            ALLOWED_REVIEW_STATUSES,
        )
    if review_status not in {"review", "reject"} and not row["canonical"]:
        issues.append(
            CanonicalAuditIssue(
                code="empty_canonical",
                message="review_status=keep requires canonical",
                row_numbers=[row_number],
                raw=raw,
            )
        )

    priority = row["priority"]
    try:
        numeric_priority = int(priority)
    except ValueError:
        numeric_priority = None
    if numeric_priority is None or not 0 <= numeric_priority <= 100:
        issues.append(
            CanonicalAuditIssue(
                code="invalid_priority",
                message="priority must be an integer from 0 through 100",
                row_numbers=[row_number],
                raw=raw,
                details={"value": priority},
            )
        )

    allowed_fields = (
        ("lang", ALLOWED_LANGS),
        ("slot", ALLOWED_SLOTS),
        ("rule_type", ALLOWED_RULE_TYPES),
        ("ambiguity", ALLOWED_AMBIGUITY),
    )
    for field_name, allowed in allowed_fields:
        value = row[field_name]
        if value and value not in allowed:
            _invalid_set_issue(
                issues, row_number, raw, field_name, value, allowed
            )

    if not row["source"]:
        issues.append(
            CanonicalAuditIssue(
                code="empty_source",
                message="source must not be empty",
                row_numbers=[row_number],
                raw=raw,
            )
        )
    elif row["source"] not in ALLOWED_SOURCES:
        _invalid_set_issue(
            issues,
            row_number,
            raw,
            "source",
            row["source"],
            ALLOWED_SOURCES,
        )

    tags = row["tags"]
    if tags and not TAG_RE.fullmatch(tags):
        issues.append(
            CanonicalAuditIssue(
                code="invalid_tags",
                message="tags must be lowercase slash-separated identifiers",
                severity="warning",
                row_numbers=[row_number],
                raw=raw,
                details={"value": tags},
            )
        )

    if row["rule_type"] == "weak_token" and review_status == "keep":
        issues.append(
            CanonicalAuditIssue(
                code="weak_token_keep",
                message="weak_token is active in runtime normalization",
                severity="warning",
                row_numbers=[row_number],
                raw=raw,
            )
        )
    if row["rule_type"] == "ambiguous_single" and review_status == "keep":
        issues.append(
            CanonicalAuditIssue(
                code="ambiguous_single_keep",
                message="ambiguous_single is active in runtime normalization",
                severity="warning",
                row_numbers=[row_number],
                raw=raw,
            )
        )
    if row["ambiguity"] == "high" and not row["note"]:
        issues.append(
            CanonicalAuditIssue(
                code="high_ambiguity_without_note",
                message="ambiguity=high should explain the review context in note",
                severity="warning",
                row_numbers=[row_number],
                raw=raw,
            )
        )


def _invalid_set_issue(
    issues: list[CanonicalAuditIssue],
    row_number: int,
    raw: str,
    field_name: str,
    value: str,
    allowed: set[str],
) -> None:
    issues.append(
        CanonicalAuditIssue(
            code=f"invalid_{field_name}",
            message=f"{field_name} is outside the allowed set",
            row_numbers=[row_number],
            raw=raw,
            details={"value": value, "allowed": sorted(allowed)},
        )
    )


def _audit_duplicates(
    rows: list[tuple[int, dict[str, str]]],
    issues: list[CanonicalAuditIssue],
) -> list[CanonicalConflict]:
    exact_rows: dict[tuple[str, ...], list[int]] = defaultdict(list)
    raw_rows: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
    for row_number, row in rows:
        signature = tuple(row[column] for column in CANONICAL_COLUMNS)
        exact_rows[signature].append(row_number)
        if row["raw"]:
            raw_rows[row["raw"].casefold()].append((row_number, row))

    for signature, row_numbers in exact_rows.items():
        if len(row_numbers) > 1:
            issues.append(
                CanonicalAuditIssue(
                    code="duplicate_row",
                    message="Rows are completely identical",
                    row_numbers=row_numbers,
                    raw=signature[0],
                )
            )

    conflicts: list[CanonicalConflict] = []
    for occurrences in raw_rows.values():
        if len(occurrences) <= 1:
            continue
        row_numbers = [row_number for row_number, _row in occurrences]
        raw = occurrences[0][1]["raw"]
        issues.append(
            CanonicalAuditIssue(
                code="duplicate_raw",
                message="raw appears in multiple rows",
                row_numbers=row_numbers,
                raw=raw,
            )
        )
        canonical_values = sorted(
            {row["canonical"] for _number, row in occurrences}
        )
        slot_values = sorted({row["slot"] for _number, row in occurrences})
        issue_codes = ["duplicate_raw"]
        if len(canonical_values) > 1:
            issue_codes.append("conflicting_canonical")
            issues.append(
                CanonicalAuditIssue(
                    code="conflicting_canonical",
                    message="raw maps to multiple canonical values",
                    row_numbers=row_numbers,
                    raw=raw,
                    details={"values": canonical_values},
                )
            )
        if len(slot_values) > 1:
            issue_codes.append("conflicting_slot")
            issues.append(
                CanonicalAuditIssue(
                    code="conflicting_slot",
                    message="raw maps to multiple slots",
                    row_numbers=row_numbers,
                    raw=raw,
                    details={"values": slot_values},
                )
            )
        conflicts.append(
            CanonicalConflict(
                raw=raw,
                row_numbers=row_numbers,
                canonical_values=canonical_values,
                slot_values=slot_values,
                issue_codes=issue_codes,
            )
        )
    return conflicts


def _audit_high_risk(
    rows: list[tuple[int, dict[str, str]]],
    issues: list[CanonicalAuditIssue],
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    found: set[str] = set()
    for row_number, row in rows:
        raw = row["raw"]
        if raw not in HIGH_RISK_SINGLE_CHARS:
            continue
        found.add(raw)
        outcome = "excluded_from_runtime"
        if row["review_status"] == "keep":
            outcome = "runtime_keep_warning"
            issues.append(
                CanonicalAuditIssue(
                    code="high_risk_single_keep",
                    message="high-risk single-character alias is active at runtime",
                    severity="warning",
                    row_numbers=[row_number],
                    raw=raw,
                    details={
                        "rule_type": row["rule_type"],
                        "ambiguity": row["ambiguity"],
                    },
                )
            )
        results.append(
            {
                "raw": raw,
                "row_number": row_number,
                "review_status": row["review_status"],
                "rule_type": row["rule_type"],
                "ambiguity": row["ambiguity"],
                "outcome": outcome,
            }
        )
    for raw in HIGH_RISK_SINGLE_CHARS:
        if raw in found:
            continue
        results.append(
            {
                "raw": raw,
                "row_number": None,
                "review_status": "—",
                "rule_type": "—",
                "ambiguity": "—",
                "outcome": "not_present",
            }
        )
    return results


def write_audit_outputs(
    result: CanonicalAuditResult,
    report_path: Path = DEFAULT_REPORT_PATH,
    conflict_path: Path = DEFAULT_CONFLICT_PATH,
) -> None:
    report_path = Path(report_path)
    conflict_path = Path(conflict_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    conflict_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_markdown(result), encoding="utf-8")
    with conflict_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CONFLICT_COLUMNS)
        writer.writeheader()
        writer.writerows(conflict.to_csv_row() for conflict in result.conflicts)


def _render_markdown(result: CanonicalAuditResult) -> str:
    issue_counts = ", ".join(
        f"`{code}`={count}" for code, count in sorted(result.issue_counts.items())
    ) or "none"
    lines = [
        "# Canonical Token Audit",
        "",
        f"- source: `{result.path}`",
        f"- passed: `{str(result.passed).lower()}`",
        f"- total_rows: `{result.total_rows}`",
        f"- runtime_keep_rows: `{result.runtime_keep_rows}`",
        f"- review_rows: `{result.review_rows}`",
        f"- reject_rows: `{result.reject_rows}`",
        f"- issue_count: `{result.issue_count}`",
        f"- error_count: `{result.error_count}`",
        f"- warning_count: `{result.warning_count}`",
        f"- issue_counts: {issue_counts}",
        f"- conflict_count: `{result.conflict_count}`",
        "",
        "## High-risk single-character results",
        "",
        "| raw | row | status | rule_type | ambiguity | outcome |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for item in result.high_risk_single_results:
        row_number = item["row_number"] if item["row_number"] is not None else "—"
        lines.append(
            f"| {item['raw']} | {row_number} | {item['review_status']} | "
            f"{item['rule_type']} | {item['ambiguity']} | {item['outcome']} |"
        )
    if not result.high_risk_single_results:
        lines.append("| — | — | — | — | — | no tracked rows |")

    lines.extend(
        [
            "",
            "## Issues",
            "",
            "| severity | code | rows | raw | message |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for issue in result.issues:
        rows = ",".join(str(value) for value in issue.row_numbers) or "—"
        lines.append(
            f"| {issue.severity} | {issue.code} | {rows} | {issue.raw or '—'} | "
            f"{issue.message} |"
        )
    if not result.issues:
        lines.append("| — | — | — | — | no issues |")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=DEFAULT_CANONICAL_PATH,
        help="Canonical CSV path (defaults to fxengine/data/canonical_tokens.csv)",
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--conflicts", type=Path, default=DEFAULT_CONFLICT_PATH)
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print JSON without writing markdown/conflict artifacts",
    )
    args = parser.parse_args(argv)
    result = audit_canonical_csv(args.path)
    if not args.no_write:
        write_audit_outputs(result, args.report, args.conflicts)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
