#!/usr/bin/env python3
"""SD FXName Quality Harness 0.1 — evaluate FXName translation quality."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import NllbTranslator
from glossary.fx_quality import evaluate_fx_output

CASES_CSV = ROOT / "tests" / "fxname_quality_cases.csv"
RESULTS_DIR = ROOT / "tests" / "results"


def load_cases(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def spacing_fuzz_variant(text: str) -> str:
    """Insert abnormal spaces every ~2 Chinese chars (deterministic baseline fuzz)."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return text
    parts: list[str] = []
    i = 0
    while i < len(chars):
        chunk_len = 2 if i + 2 <= len(chars) else len(chars) - i
        parts.append("".join(chars[i : i + chunk_len]))
        i += chunk_len
    return " ".join(parts)


def random_spacing_fuzz(text: str, rng: random.Random) -> str:
    """Randomly split Chinese run into 1–3 char chunks."""
    chars = [c for c in text if not c.isspace()]
    if len(chars) <= 2:
        return text
    parts: list[str] = []
    i = 0
    while i < len(chars):
        remaining = len(chars) - i
        if remaining <= 2:
            parts.append("".join(chars[i:]))
            break
        chunk_len = rng.randint(1, min(3, remaining - 1))
        parts.append("".join(chars[i : i + chunk_len]))
        i += chunk_len
    return " ".join(parts)


def expand_cases(
    rows: list[dict[str, str]], fuzz_count: int, seed: int
) -> list[dict[str, str]]:
    expanded: list[dict[str, str]] = []
    seen_inputs: set[str] = set()
    fuzz_bases: list[str] = []
    rng = random.Random(seed)

    for row in rows:
        inp = row["input"].strip()
        is_fuzz_source = row.get("spacing_fuzz_source", "").lower() in {"yes", "true", "1"}

        if is_fuzz_source:
            fuzz_bases.append(inp)

        if inp not in seen_inputs:
            seen_inputs.add(inp)
            expanded.append(
                {
                    "input": inp,
                    "case_group": row.get("case_group", ""),
                    "expected_note": row.get("expected_note", ""),
                    "source_path": "fixture",
                    "spacing_fuzz": "no",
                }
            )

        if is_fuzz_source:
            fuzz_inp = spacing_fuzz_variant(inp)
            if fuzz_inp != inp and fuzz_inp not in seen_inputs:
                seen_inputs.add(fuzz_inp)
                expanded.append(
                    {
                        "input": fuzz_inp,
                        "case_group": "spacing_fuzz",
                        "expected_note": f"auto fuzz from {inp}",
                        "source_path": "spacing_fuzz_auto",
                        "spacing_fuzz": "yes",
                    }
                )

    attempts = 0
    while fuzz_count > 0 and fuzz_bases and attempts < fuzz_count * 10:
        attempts += 1
        base = rng.choice(fuzz_bases)
        fuzz_inp = random_spacing_fuzz(base, rng)
        if fuzz_inp == base or fuzz_inp in seen_inputs:
            continue
        seen_inputs.add(fuzz_inp)
        expanded.append(
            {
                "input": fuzz_inp,
                "case_group": "spacing_fuzz_random",
                "expected_note": f"random fuzz from {base}",
                "source_path": "spacing_fuzz_random",
                "spacing_fuzz": "yes",
            }
        )
        fuzz_count -= 1

    return expanded


def row_from_result(case: dict, result) -> dict:
    debug = result.debug or {}
    is_fuzz = case.get("spacing_fuzz") == "yes"
    q = evaluate_fx_output(
        case["input"],
        result.text,
        debug=debug,
        input_is_spacing_fuzz=is_fuzz,
    )
    return {
        "input": case["input"],
        "output": result.text,
        "quality": q.quality,
        "issues": "|".join(q.issues),
        "matched_bad_phrases": "|".join(q.matched_bad_phrases),
        "output_token_count": q.output_token_count,
        "case_group": case.get("case_group", ""),
        "source_path": case.get("source_path", "fixture"),
        "expected_note": case.get("expected_note", ""),
        "spacing_fuzz": case.get("spacing_fuzz", "no"),
        "coverage": debug.get("coverage", ""),
        "unknown_zh": "|".join(debug.get("unknown_zh") or []),
        "candidate_fragments": "|".join(
            str(x) for x in (debug.get("candidate_fragments") or [])
        ),
        "slots": json.dumps(debug.get("slots") or [], ensure_ascii=False),
        "assembled_order": "|".join(debug.get("assembled_order") or []),
        "reorder_reason": debug.get("reorder_reason", ""),
        "hybrid_fallback": debug.get("hybrid_fallback", ""),
        "engine_quality": debug.get("quality", ""),
        "engine_issues": "|".join(debug.get("issues") or []),
    }


def print_summary(rows: list[dict]) -> None:
    total = len(rows)
    pass_n = sum(1 for r in rows if r["quality"] == "pass")
    review_n = sum(1 for r in rows if r["quality"] == "needs_review")
    fail_n = sum(1 for r in rows if r["quality"] == "fail")
    bad_phrase_count = sum(
        1 for r in rows if "bad_phrase" in r.get("issues", "")
    )
    unknown_count = sum(1 for r in rows if "unknown_zh" in r.get("issues", ""))
    mixed_count = sum(
        1 for r in rows if "mixed_language_residue" in r.get("issues", "")
    )
    empty_count = sum(1 for r in rows if "empty_output" in r.get("issues", ""))
    avg_tokens = (
        round(sum(int(r["output_token_count"]) for r in rows) / total, 2)
        if total
        else 0
    )

    print("=== FXName Quality Summary ===")
    print(f"total:              {total}")
    print(f"pass:               {pass_n}")
    print(f"needs_review:       {review_n}")
    print(f"fail:               {fail_n}")
    print(f"bad_phrase_count:   {bad_phrase_count}")
    print(f"unknown_count:      {unknown_count}")
    print(f"mixed_residue_count:{mixed_count}")
    print(f"empty_count:        {empty_count}")
    print(f"average_output_tokens: {avg_tokens}")


def write_csv(rows: list[dict], path: Path) -> None:
    fields = [
        "input",
        "output",
        "quality",
        "issues",
        "matched_bad_phrases",
        "output_token_count",
        "case_group",
        "source_path",
        "expected_note",
        "spacing_fuzz",
        "coverage",
        "unknown_zh",
        "candidate_fragments",
        "slots",
        "assembled_order",
        "reorder_reason",
        "hybrid_fallback",
        "engine_quality",
        "engine_issues",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _section_table(rows: list[dict], title: str) -> list[str]:
    lines = [f"## {title}", ""]
    if not rows:
        lines.append("（无）")
        lines.append("")
        return lines
    lines.extend(
        [
            "| input | output | quality | issues | matched_bad_phrases |",
            "|---|---|---|---|---|",
        ]
    )
    for row in rows:
        out = row["output"].replace("|", "\\|")
        lines.append(
            f"| {row['input']} | `{out}` | {row['quality']} | "
            f"{row['issues'] or '-'} | {row['matched_bad_phrases'] or '-'} |"
        )
    lines.append("")
    return lines


def write_markdown(rows: list[dict], path: Path, fuzz_count: int) -> None:
    total = len(rows)
    pass_n = sum(1 for r in rows if r["quality"] == "pass")
    review_n = sum(1 for r in rows if r["quality"] == "needs_review")
    fail_n = sum(1 for r in rows if r["quality"] == "fail")
    bad_phrase_count = sum(
        1 for r in rows if "bad_phrase" in r.get("issues", "")
    )
    unknown_count = sum(1 for r in rows if "unknown_zh" in r.get("issues", ""))
    mixed_count = sum(
        1 for r in rows if "mixed_language_residue" in r.get("issues", "")
    )
    empty_count = sum(1 for r in rows if "empty_output" in r.get("issues", ""))
    avg_tokens = (
        round(sum(int(r["output_token_count"]) for r in rows) / total, 2)
        if total
        else 0
    )

    fail_sorted = sorted(
        rows,
        key=lambda r: (
            0 if r["quality"] == "fail" else 1 if r["quality"] == "needs_review" else 2,
            -len(r.get("issues", "").split("|")) if r.get("issues") else 0,
            r["input"],
        ),
    )
    worst_20 = fail_sorted[:20]

    lines = [
        "# SD FXName Quality Harness 0.1 报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 用例数：{total}（随机 fuzz 追加：{fuzz_count}）",
        "",
        "## Summary",
        "",
        f"- total: **{total}**",
        f"- pass: **{pass_n}** ({100 * pass_n / total:.1f}%)" if total else "- pass: 0",
        f"- needs_review: **{review_n}**",
        f"- fail: **{fail_n}**",
        f"- bad_phrase_count: **{bad_phrase_count}**",
        f"- unknown_count: **{unknown_count}**",
        f"- mixed_residue_count: **{mixed_count}**",
        f"- empty_count: **{empty_count}**",
        f"- average_output_tokens: **{avg_tokens}**",
        "",
    ]

    issue_counts = Counter()
    for row in rows:
        for issue in row.get("issues", "").split("|"):
            if issue:
                issue_counts[issue] += 1
    if issue_counts:
        lines.extend(["## Issue 分布", ""])
        for issue, count in issue_counts.most_common():
            lines.append(f"- **{issue}**: {count}")
        lines.append("")

    lines.extend(["## Top failures（最差 20 条）", ""])
    for i, row in enumerate(worst_20, 1):
        lines.append(f"### {i}. {row['input']}")
        lines.append(f"- output: `{row['output']}`")
        lines.append(f"- quality: **{row['quality']}** | group: {row['case_group']}")
        lines.append(f"- issues: {row['issues'] or '（无）'}")
        lines.append(f"- matched_bad_phrases: {row['matched_bad_phrases'] or '（无）'}")
        lines.append("")

    bad_rows = [r for r in rows if "bad_phrase" in r.get("issues", "")]
    unknown_rows = [r for r in rows if "unknown_zh" in r.get("issues", "")]
    mixed_rows = [r for r in rows if "mixed_language_residue" in r.get("issues", "")]
    fuzz_rows = [r for r in rows if r.get("case_group", "").startswith("spacing_fuzz")]
    regression_rows = [
        r
        for r in rows
        if r["case_group"] in {"problem_sample", "mixed_english"}
        and r["quality"] != "pass"
    ]

    lines.extend(_section_table(bad_rows, "Bad phrase cases"))
    lines.extend(_section_table(unknown_rows, "Unknown zh cases"))
    lines.extend(_section_table(mixed_rows, "Mixed English / 中文残留 cases"))
    lines.extend(_section_table(fuzz_rows, "Spacing fuzz cases"))
    lines.extend(_section_table(regression_rows, "Regression examples"))

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate FXName translation quality")
    parser.add_argument(
        "--cases",
        type=Path,
        default=CASES_CSV,
        help="Fixture CSV path",
    )
    parser.add_argument(
        "--fuzz",
        type=int,
        default=0,
        help="Extra random spacing fuzz cases",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for fuzz generation",
    )
    args = parser.parse_args()

    raw_cases = load_cases(args.cases)
    cases = expand_cases(raw_cases, args.fuzz, args.seed)
    print(f"Loaded {len(raw_cases)} fixture rows -> {len(cases)} evaluation cases")

    translator = NllbTranslator()
    print("Loading model...")
    translator.load()

    rows: list[dict] = []
    for i, case in enumerate(cases, 1):
        result = translator.translate(
            case["input"], mode="sentence", pro_mode=True, task_mode="fxname"
        )
        rows.append(row_from_result(case, result))
        if i % 10 == 0 or i == len(cases):
            print(f"  translated {i}/{len(cases)}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = RESULTS_DIR / f"fxname_quality_{ts}.csv"
    md_path = RESULTS_DIR / f"fxname_quality_{ts}.md"
    latest_csv = RESULTS_DIR / "fxname_quality_latest.csv"
    latest_md = RESULTS_DIR / "fxname_quality_latest.md"

    write_csv(rows, csv_path)
    write_csv(rows, latest_csv)
    write_markdown(rows, md_path, args.fuzz)
    write_markdown(rows, latest_md, args.fuzz)

    print_summary(rows)
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")
    print(f"Latest: {latest_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
