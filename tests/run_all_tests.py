#!/usr/bin/env python3
"""全量体验测试：英→中、中→英、文件名模式。结果写入 tests/results/。"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = Path(__file__).resolve().parent / "results"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import NllbTranslator


@dataclass
class Case:
    id: str
    category: str
    input: str
    must_contain: list[str] = field(default_factory=list)
    must_not_contain: list[str] = field(default_factory=list)
    mode: str = "auto"
    pro_mode: bool = True
    min_hits: int = 0


@dataclass
class CaseResult:
    id: str
    category: str
    input: str
    output: str
    status: str  # PASS | PARTIAL | FAIL
    status_label: str
    glossary_hits: int
    missing: list[str]
    forbidden_found: list[str]
    notes: str = ""


CASES: list[Case] = [
    # ── 英→中 文件名 ──
    Case("fn-001", "英→中·文件名", "ICEFric_Ice Axe Scratch Friction Ice Brick 01_ASO_Rec_CO100K",
         ["冰斧", "刮擦", "ICEFric", "ASO", "CO100K"], ["澳门"]),
    Case("fn-002", "英→中·文件名", "WEAPBow_Nocked longcompoundbow leatherrest drawing_B00M_JSE.wav",
         ["搭箭", "复合长弓", "皮托", "B00M", "JSE"], ["美国", "书写"]),
    Case("fn-003", "英→中·文件名", "VEHCar_Porsche 911 driveby exterior revving_B00M_ASO.wav",
         ["保时捷", "驶过", "室外", "B00M", "ASO"], ["澳门"]),
    Case("fn-004", "英→中·文件名", "AMBDsgn_Decid forest dawn birds QP08.wav",
         ["落叶林", "森林", "QP08"], []),
    Case("fn-005", "英→中·文件名", "GUNCano_FIRING 16 Pounder flyby mono_B00M_CACK_ORTF3D Hi.wav",
         ["飞越", "B00M", "CACK", "ORTF3D"], ["您好", "机枪"], min_hits=1),
    Case("fn-006", "英→中·文件名", "FOODDrnk_Espresso machine insert steam hiss_B00M.wav",
         ["浓缩咖啡", "插入", "B00M"], []),
    # ── 英→中 句子 ──
    Case("en-001", "英→中·句子", "Exterior reverberant room tone with idle engine rev",
         ["室外", "有混响", "房间底噪", "怠速"], []),
    Case("en-002", "英→中·句子", "Shooter nocked arrow with continuous echoing decay",
         ["射手", "搭箭", "持续", "有回声", "衰减"], []),
    Case("en-003", "英→中·句子", "Whip-panning wipe with punchy transient",
         ["甩镜", "划变", "冲击"], []),
    Case("en-004", "英→中·句子", "Early morning conif forests with croak and insects",
         ["针叶林", "森林", "蛙鸣", "昆虫"], []),
    Case("en-005", "英→中·句子", "Room tone of empty office with steady hum",
         ["房间底噪", "办公室"], []),
    Case("en-006", "英→中·句子", "Whoosh and swish flyby exterior",
         ["呼啸", "嗖嗖", "飞越", "室外"], []),
    # ── 中→英 FX 组装 ──
    Case("zh-001", "中→英·FX", "冰斧刮擦冰砖的摩擦声",
         ["Ice Axe", "Scratch", "Ice Brick", "Friction"], ["Newspaper", "Oh"]),
    Case("zh-002", "中→英·FX", "拧螺丝，咔哒几声，然后关上",
         ["Screw", "Clicks", "Close"], ["God", "Lord"]),
    Case("zh-003", "中→英·FX", "外面汽车开过去呼呼的，带混响",
         ["Exterior", "Car", "Driveby", "Whoosh", "Reverberant"], []),
    Case("zh-004", "中→英·FX", "弓搭箭，皮托，拉弦",
         ["Bow", "Nocked", "Leatherrest", "Drawing"], ["Lord"]),
    Case("zh-005", "中→英·FX", "空办公室里的房间底噪，有一点混响",
         ["Empty", "Office", "Room Tone", "Reverberant"], ["Conservatory"]),
    Case("zh-006", "中→英·FX", "落叶林清晨鸟叫，偶尔有蛙鸣",
         ["Decid", "Birds", "Croak"], []),
    Case("zh-007", "中→英·FX", "保时捷从外面轰油门快速驶过",
         ["Porsche", "Exterior", "Driveby"], []),
    Case("zh-008", "中→英·FX", "单声道室外混响底噪",
         ["Mono", "Exterior", "Reverberant", "Room Tone"], []),
    Case("zh-009", "中→英·FX", "关门声关闭 exterior shut",
         ["Close", "Exterior", "Shut"], []),
    Case("zh-010", "中→英·FX", "拟音衣物摩擦掉落",
         ["Foley", "Clothes", "Rub", "Drop"], []),
    Case("zh-011", "中→英·FX", "竹子弓箭搭箭",
         ["Bamboo", "Bow", "Nocked"], []),
    Case("zh-012", "中→英·FX", "引擎怠速轰油门",
         ["Idle", "Rev"], []),
    # ── 口语化 ──
    Case("zh-o1", "中→英·口语", "嗖的一声飞过去",
         ["Swish", "Flyby"], []),
    Case("zh-o2", "中→英·口语", "咔哒关上门",
         ["Clicks", "Close", "Door"], []),
    Case("zh-o3", "中→英·口语", "户外虫鸣昆虫",
         ["Outdoor", "Insects"], []),
    Case("zh-o4", "中→英·口语", "木地板脚步 parquet",
         ["Parquet"], []),
    # ── 保护码不译 ──
    Case("fn-007", "英→中·保护码", "TEST_ASO_B00M_JSE_CO100K.wav",
         ["ASO", "B00M", "JSE", "CO100K"], ["澳门", "美国"]),
    # ── 扩展用例 ──
    Case("fn-008", "英→中·文件名", "WPNBow_Arrow nocked bamboo longcompoundbow_B00M.wav",
         ["搭箭", "竹子", "B00M"], []),
    Case("fn-009", "英→中·文件名", "AMBForst_conif forest morning birds croak_QP11.wav",
         ["针叶林", "森林", "蛙鸣", "QP11"], []),
    Case("en-007", "英→中·句子", "Generic impact clicks with bright thin tone",
         ["通用", "咔哒", "明亮", "纤细"], []),
    Case("en-008", "英→中·句子", "Driveby exterior porsche revving idle",
         ["驶过", "室外", "保时捷", "轰油门", "怠速"], []),
    Case("zh-013", "中→英·FX", "通用撞击明亮音色",
         ["Generic", "Impact", "Bright"], []),
    Case("zh-014", "中→英·FX", "有混响的室外房间底噪",
         ["Reverberant", "Exterior", "Room Tone"], []),
    Case("zh-015", "中→英·FX", "针叶林落叶林森林",
         ["Conif", "Decid", "Forest"], []),
    Case("zh-o5", "中→英·口语", "轰油门怠速引擎声",
         ["Rev", "Idle", "Engine"], []),
    Case("zh-o6", "中→英·口语", "冰砖冰斧刮擦",
         ["Ice Brick", "Ice Axe", "Scratch"], []),
    Case("zh-o7", "中→英·口语", "关门关闭 shut",
         ["Close", "Shut"], []),
    Case("fn-010", "英→中·文件名", "VEHMisc_GAZ 53B horn exterior_B00M.wav",
         ["嘎斯", "室外", "B00M"], []),
]


def evaluate(case: Case, output: str, hits: int) -> CaseResult:
    out_lower = output.lower()
    missing = [w for w in case.must_contain if w.lower() not in out_lower]
    forbidden = [w for w in case.must_not_contain if w.lower() in out_lower]

    if forbidden:
        status = "FAIL"
    elif not missing and hits >= case.min_hits:
        status = "PASS"
    elif missing and len(missing) < len(case.must_contain):
        status = "PARTIAL"
    else:
        status = "FAIL"

    notes = []
    if hits < case.min_hits:
        notes.append(f"术语命中 {hits} < 期望 {case.min_hits}")

    return CaseResult(
        id=case.id,
        category=case.category,
        input=case.input,
        output=output,
        status=status,
        status_label="",
        glossary_hits=hits,
        missing=missing,
        forbidden_found=forbidden,
        notes="; ".join(notes),
    )


def run_all() -> tuple[list[CaseResult], dict]:
    t = NllbTranslator()
    t.load()
    results: list[CaseResult] = []
    for case in CASES:
        r = t.translate(case.input, mode=case.mode, pro_mode=case.pro_mode)
        cr = evaluate(case, r.text, r.glossary_hits)
        cr.status_label = r.status_label
        results.append(cr)
    stats = {
        "total": len(results),
        "pass": sum(1 for x in results if x.status == "PASS"),
        "partial": sum(1 for x in results if x.status == "PARTIAL"),
        "fail": sum(1 for x in results if x.status == "FAIL"),
        "pass_rate": round(100 * sum(1 for x in results if x.status == "PASS") / len(results), 1),
        "ok_rate": round(100 * sum(1 for x in results if x.status in ("PASS", "PARTIAL")) / len(results), 1),
    }
    return results, stats


def write_reports(results: list[CaseResult], stats: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RESULTS_DIR / f"run_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    payload = {"generated_at": ts, "stats": stats, "results": [asdict(r) for r in results]}
    json_path = run_dir / "report.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown
    lines = [
        f"# LocalTranslate 测试报告",
        f"",
        f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 总计: {stats['total']} | PASS: {stats['pass']} | PARTIAL: {stats['partial']} | FAIL: {stats['fail']}",
        f"- 通过率: {stats['pass_rate']}% | 可用率(PASS+PARTIAL): {stats['ok_rate']}%",
        f"",
    ]
    by_cat: dict[str, list[CaseResult]] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)

    for cat, items in by_cat.items():
        lines.append(f"## {cat}")
        lines.append("")
        for r in items:
            icon = {"PASS": "✅", "PARTIAL": "⚠️", "FAIL": "❌"}.get(r.status, "?")
            lines.append(f"### {icon} `{r.id}` — {r.status}")
            lines.append(f"- 输入: `{r.input}`")
            lines.append(f"- 输出: `{r.output}`")
            lines.append(f"- 模式: {r.status_label} | 术语命中: {r.glossary_hits}")
            if r.missing:
                lines.append(f"- 缺少: {', '.join(r.missing)}")
            if r.forbidden_found:
                lines.append(f"- 不应出现: {', '.join(r.forbidden_found)}")
            if r.notes:
                lines.append(f"- 备注: {r.notes}")
            lines.append("")

    fails = [r for r in results if r.status == "FAIL"]
    if fails:
        lines.append("## 待修复清单")
        lines.append("")
        for r in fails:
            lines.append(f"- `{r.id}`: 缺 {r.missing or '-'} | 禁 {r.forbidden_found or '-'}")

    md_path = run_dir / "report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # latest  symlink copies
    latest_md = RESULTS_DIR / "latest_report.md"
    latest_json = RESULTS_DIR / "latest_report.json"
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")

    summary = RESULTS_DIR / "README.md"
    summary.write_text(
        "# 测试结果目录\n\n"
        "每次运行 `python tests/run_all_tests.py` 会在此生成：\n\n"
        "- `latest_report.md` — 最新报告（推荐先看）\n"
        "- `latest_report.json` — 机器可读\n"
        "- `run_YYYYMMDD_HHMMSS/` — 历史快照\n\n"
        f"最近一次: **{stats['pass_rate']}% PASS**, **{stats['ok_rate']}% 可用** ({stats['total']} 条)\n",
        encoding="utf-8",
    )
    return run_dir


def main() -> int:
    print("Loading model and running tests...")
    results, stats = run_all()
    run_dir = write_reports(results, stats)
    print(f"PASS {stats['pass']}/{stats['total']} ({stats['pass_rate']}%)")
    print(f"OK   {stats['pass']+stats['partial']}/{stats['total']} ({stats['ok_rate']}%)")
    print(f"Report: {run_dir / 'report.md'}")
    print(f"Latest: {RESULTS_DIR / 'latest_report.md'}")
    return 0 if stats["fail"] <= stats["total"] * 0.15 else 1


if __name__ == "__main__":
    raise SystemExit(main())
