"""模式1：中文 / 中英混合 -> BOOM 风格 FXName 关键词英文。

管线：分词(保护ASCII/数字) -> 逐 token 译(canonical覆盖 > CC-CEDICT > NLLB兜底)
       -> BOOM 风格吸附 -> 关键词化 -> 复用 fx_slots 组装。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from glossary.fx_slots import SlotTerm, assemble_fx_name, infer_slot

from translator import boom_snap, cedict, overrides
from translator import segment as seg

# 中文功能词：翻译前直接丢弃（含易被 cedict 误义的定位/时间虚词 里/后）
ZH_STOP = set("的了着和与在是得地及并或之而其也都很就里后")
# 英文虚词：翻译后关键词化时丢弃（保留 on/off/up/down/over/out/away/by/in 等有义介词）
EN_DROP = {
    "the", "a", "an", "of", "and", "is", "are", "was", "were", "be", "been",
    "to", "that", "this", "it", "its", "with", "into", "from", "as", "for",
    "their", "his", "her", "they", "you", "we",
}

_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+\-]*")


@dataclass
class TokenTrace:
    source_text: str
    kind: str
    translated: str = ""
    snapped: str = ""
    decision: str = ""
    detail: str = ""
    final_words: list[str] = field(default_factory=list)


@dataclass
class FXResult:
    output_fxname: str
    traces: list[TokenTrace]


def _title(word: str) -> str:
    if any(c.isdigit() for c in word):
        return word  # 型号码 / 编号 / 距离（A109、01、150m）原样保留
    if word.lower() in {"fx", "sfx", "ucs"}:
        return word.upper()
    return word[:1].upper() + word[1:].lower()


def _translate_zh_token(tok: str) -> tuple[str, str, str | None]:
    """返回 (english, source, slot_hint)。"""
    entry = overrides.lookup(tok)
    if entry:
        return entry["canonical"], "override", entry.get("slot") or None
    gloss = cedict.lookup(tok)
    if gloss:
        return gloss, "cedict", None
    try:
        from translator import nllb

        english = nllb.zh2en(tok)
    except Exception:
        english = ""
    if english:
        return english, "nllb", None
    return "", "unknown", None


def normalize(text: str) -> FXResult:
    traces: list[TokenTrace] = []
    terms: list[SlotTerm] = []
    group = 0

    segments = seg.segment(text)
    i = 0
    while i < len(segments):
        s = segments[i]
        if s.kind == "ascii":
            words = [_title(w) for w in _WORD_RE.findall(s.text)]
            if not words:
                i += 1
                continue
            trace = TokenTrace(s.text, "ascii", translated=s.text, snapped=s.text,
                               decision="protected", final_words=words)
            traces.append(trace)
            for w in words:
                slot = infer_slot(w)
                terms.append(SlotTerm(w, slot if slot != "unknown" else "detail",
                                      "protected", group))
            group += 1
            i += 1
            continue

        if s.text in ZH_STOP or all(c in ZH_STOP for c in s.text):
            traces.append(TokenTrace(s.text, "zh", decision="dropped_stop"))
            i += 1
            continue

        # 短语(2-gram)覆盖：相邻两个中文词若命中，优先用上下文译法（多义词消歧）
        if i + 1 < len(segments) and segments[i + 1].kind == "zh":
            phrase_en = overrides.phrase_lookup(s.text, segments[i + 1].text)
            if phrase_en:
                src = f"{s.text} {segments[i + 1].text}"
                words = [_title(w) for w in _WORD_RE.findall(phrase_en)]
                trace = TokenTrace(src, "zh", translated=phrase_en, snapped=phrase_en,
                                   decision="phrase", final_words=words)
                traces.append(trace)
                for w in words:
                    slot = infer_slot(w)
                    terms.append(SlotTerm(w, slot if slot != "unknown" else "detail",
                                          "phrase", group))
                group += 1
                i += 2
                continue

        english, source, slot_hint = _translate_zh_token(s.text)
        trace = TokenTrace(s.text, "zh", translated=english, decision=source)
        if not english:
            traces.append(trace)
            i += 1
            continue

        snap = boom_snap.snap_term(english, s.text, trust=(source == "override"))
        trace.snapped = snap.final
        trace.decision = f"{source}+{snap.decision}"
        trace.detail = snap.detail

        kept = [w for w in _WORD_RE.findall(snap.final) if w.lower() not in EN_DROP]
        if not kept:
            kept = [w for w in _WORD_RE.findall(snap.final)]
        if not kept:
            traces.append(trace)
            i += 1
            continue
        trace.final_words = [_title(w) for w in kept]
        traces.append(trace)
        for w in trace.final_words:
            slot = infer_slot(w, slot_hint)
            terms.append(SlotTerm(w, slot if slot != "unknown" else (slot_hint or "unknown"),
                                  source, group))
        group += 1
        i += 1

    assembled = assemble_fx_name(terms, preserve_order=True)
    return FXResult(output_fxname=assembled.text, traces=traces)


if __name__ == "__main__":
    samples = [
        "喷火器",
        "遥控无人机起飞",
        "奥古斯塔 A109 飞走 01",
        "金属门重重关上",
        "远处雷声沉闷的轰鸣",
        "玻璃杯清脆碰撞",
    ]
    for s in samples:
        r = normalize(s)
        print(f"\n输入: {s}")
        print(f"输出: {r.output_fxname}")
        for t in r.traces:
            print(f"   [{t.kind}] {t.source_text!r} -> {t.translated!r} => {t.snapped!r} "
                  f"[{t.decision}] {t.detail}")
