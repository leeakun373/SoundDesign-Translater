#!/usr/bin/env python3
"""Run smoke_real_cases.csv through engine and export slot-aware FX report (temporary)."""

from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import NllbTranslator

CASES_CSV = ROOT / "tests" / "smoke_real_cases.csv"
RESULTS_DIR = ROOT / "tests" / "results"
SLOT_ORDER = (
    "modifier",
    "design",
    "material",
    "object",
    "source",
    "creature_sound",
    "action",
    "detail",
    "unknown",
)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-]*")
SENTENCE_VERBS = re.compile(
    r"\b(?:slipped|slides|sliding|opened|opens|pushed|pushes|pulled|pulls)\b",
    re.IGNORECASE,
)


def load_cases() -> list[dict[str, str]]:
    with CASES_CSV.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _slot_index(slot: str) -> int:
    try:
        return SLOT_ORDER.index(slot)
    except ValueError:
        return SLOT_ORDER.index("unknown")


def flag_issues(
    input_text: str, output: str, debug: dict, expected_note: str
) -> list[str]:
    flags: list[str] = []
    issues = debug.get("issues") or []
    unknown = debug.get("unknown_zh") or []
    coverage = float(debug.get("coverage") or 0)
    slots = debug.get("slots") or []
    assembled = debug.get("assembled_order") or []
    out_lower = output.lower()
    words = WORD_RE.findall(output)

    for issue in issues:
        if issue.startswith("missing:"):
            flags.append("输出缺核心词")
        elif issue == "natural_sentence":
            flags.append("输出自然句")
        elif issue == "low_information":
            flags.append("过度压缩")

    if len(unknown) >= 2 or (unknown and coverage < 0.75):
        flags.append("unknown_zh过多")
    elif unknown:
        flags.append("unknown_zh")

    if slots:
        indexed = [(i, s.get("slot", "unknown"), s.get("token", "")) for i, s in enumerate(slots)]
        mat_idxs = [i for i, slot, _ in indexed if slot == "material"]
        obj_idxs = [i for i, slot, _ in indexed if slot == "object"]
        act_idxs = [i for i, slot, _ in indexed if slot == "action"]
        if mat_idxs and obj_idxs and min(mat_idxs) > min(obj_idxs):
            flags.append("material/object顺序错误")
        if obj_idxs and act_idxs and min(act_idxs) < max(obj_idxs):
            flags.append("object/action顺序错误")

    if "盒" in input_text and "drop box" in out_lower:
        if out_lower.find("box") > out_lower.find("drop"):
            flags.append("object/action顺序错误")
    if ("水流" in input_text or "流过" in input_text) and out_lower in {"flow stone", "flow"}:
        flags.append("过度压缩")
    if ("水流" in input_text or "流过" in input_text) and "water" not in out_lower:
        flags.append("输出缺核心词")

    if output.strip().endswith((".", "?", "!")) or SENTENCE_VERBS.search(output):
        if "输出自然句" not in flags:
            flags.append("输出自然句")
    if re.match(r"^(the|a|an)\s", output, re.I):
        flags.append("不符合Boom命名习惯")
    if len(words) > 8:
        flags.append("不符合Boom命名习惯")
    if len(input_text) >= 6 and len(words) <= 2 and "过度压缩" not in flags:
        if any(ch in input_text for ch in "过掉落破碎推开拉开摩擦刮擦"):
            flags.append("过度压缩")

    if debug.get("quality") == "fail" and not flags:
        flags.append("quality_fail")

    deduped: list[str] = []
    for flag in flags:
        if flag not in deduped:
            deduped.append(flag)
    return deduped


def row_from_result(case: dict, result) -> dict:
    debug = result.debug or {}
    flags = flag_issues(case["input"], result.text, debug, case.get("expected_note", ""))
    return {
        "input": case["input"],
        "expected_note": case.get("expected_note", ""),
        "output": result.text,
        "quality": debug.get("quality", ""),
        "issues": "|".join(debug.get("issues") or []),
        "coverage": debug.get("coverage", ""),
        "unknown_zh": "|".join(debug.get("unknown_zh") or []),
        "candidate_fragments": "|".join(debug.get("candidate_fragments") or []),
        "slots": json.dumps(debug.get("slots") or [], ensure_ascii=False),
        "assembled_order": "|".join(debug.get("assembled_order") or []),
        "reorder_reason": debug.get("reorder_reason", ""),
        "boom_phrase_hits": "|".join(debug.get("boom_phrase_hits") or []),
        "flags": "|".join(flags),
        "glossary_hits": debug.get("glossary_hits", result.glossary_hits),
        "hybrid_fallback": debug.get("hybrid_fallback", ""),
    }


def write_csv(rows: list[dict], path: Path) -> None:
    fields = [
        "input",
        "expected_note",
        "output",
        "quality",
        "issues",
        "coverage",
        "unknown_zh",
        "candidate_fragments",
        "slots",
        "assembled_order",
        "reorder_reason",
        "boom_phrase_hits",
        "flags",
        "glossary_hits",
        "hybrid_fallback",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict], path: Path) -> None:
    flagged = [r for r in rows if r["flags"]]
    pass_n = sum(1 for r in rows if r["quality"] == "pass")
    lines = [
        "# Slot-aware FXName Smoke 报告（真实命名）",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 用例数：{len(rows)}",
        f"- quality=pass：{pass_n}/{len(rows)} ({100*pass_n/len(rows):.1f}%)",
        f"- 有标记问题：{len(flagged)}",
        "",
        "## 汇总标记",
        "",
    ]
    flag_counts: dict[str, int] = {}
    for row in flagged:
        for flag in row["flags"].split("|"):
            if flag:
                flag_counts[flag] = flag_counts.get(flag, 0) + 1
    for flag, count in sorted(flag_counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- **{flag}**：{count}")

    lines.extend(["", "## 重点用例", ""])
    focus_inputs = [
        "塑料盒掉落",
        "水流过石头",
        "玻璃杯子掉落破碎",
        "布椅子拖动摩擦",
        "木门滑开",
        "冰斧刮擦冰砖",
        "保时捷外面轰油门驶过",
        "大炮发射飞过",
    ]
    for inp in focus_inputs:
        row = next((r for r in rows if r["input"] == inp), None)
        if not row:
            continue
        lines.append(f"### {inp}")
        lines.append(f"- expected_note: {row['expected_note']}")
        lines.append(f"- output: `{row['output']}`")
        lines.append(f"- quality: {row['quality']} | reorder: {row['reorder_reason']}")
        lines.append(f"- assembled_order: {row['assembled_order']}")
        lines.append(f"- slots: {row['slots']}")
        lines.append(f"- flags: {row['flags'] or '（无）'}")
        lines.append("")

    lines.extend(["", "## 全部标记问题用例", "", "| input | output | flags | reorder |", "|---|---|---|---|"])
    for row in flagged:
        out = row["output"].replace("|", "\\|")
        lines.append(
            f"| {row['input']} | `{out}` | {row['flags']} | {row['reorder_reason']} |"
        )

    lines.extend(["", "## 全量结果", "", "| # | input | output | quality | flags |", "|---:|---|---|---|---|"])
    for i, row in enumerate(rows, 1):
        out = row["output"].replace("|", "\\|")
        lines.append(
            f"| {i} | {row['input']} | `{out}` | {row['quality']} | {row['flags'] or '-'} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    cases = load_cases()
    print(f"Loaded {len(cases)} cases from {CASES_CSV}")
    translator = NllbTranslator()
    translator.load()

    rows: list[dict] = []
    for case in cases:
        r = translator.translate(case["input"], mode="sentence", pro_mode=True)
        rows.append(row_from_result(case, r))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RESULTS_DIR / f"smoke_real_cases_{ts}.csv"
    md_path = RESULTS_DIR / f"smoke_real_cases_{ts}.md"
    latest_csv = RESULTS_DIR / "smoke_real_cases_latest.csv"
    latest_md = RESULTS_DIR / "smoke_real_cases_latest.md"

    write_csv(rows, csv_path)
    write_csv(rows, latest_csv)
    write_markdown(rows, md_path)
    write_markdown(rows, latest_md)

    flagged = sum(1 for r in rows if r["flags"])
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")
    print(f"Latest: {latest_csv}")
    print(f"pass={sum(1 for r in rows if r['quality']=='pass')}/{len(rows)} flagged={flagged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
