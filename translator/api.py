"""统一离线翻译入口：4 种能力一个接口。

- to_fxname(zh)      : 模式1 中文/混合 -> BOOM 风格 FXName 关键词英文
- zh_to_en(text)     : 模式3 中文 -> 英文整句（写 metadata 描述用）
- en_to_zh(text)     : 模式2/4 英文 -> 中文（词/句，意思到位即可）
- translate(text, task=...): 统一分发

模式2/3/4 复用 engine.py 的 NLLB + 术语库（glossary）路径；模式1 走 fxname_mode。
"""

from __future__ import annotations

from dataclasses import dataclass

from engine import EN_LANG, ZH_LANG, TaskMode, TranslateMode

from translator import fxname_mode
from translator import nllb


@dataclass
class TranslateResult:
    text: str
    task: str
    detail: object = None


def to_fxname(text: str) -> TranslateResult:
    res = fxname_mode.normalize(text)
    return TranslateResult(res.output_fxname, "fxname", res)


def _general(text: str, src: str, tgt: str) -> str:
    """复用 engine 的 general + glossary 句子翻译；失败回退裸 NLLB。"""
    try:
        engine = nllb._engine()
        result = engine.translate(
            text,
            src_lang=src,
            tgt_lang=tgt,
            mode=TranslateMode.SENTENCE,
            task_mode=TaskMode.GENERAL,
            pro_mode=True,
        )
        if result.text.strip():
            return result.text
    except Exception:
        pass
    return nllb.zh2en(text) if (src == ZH_LANG) else nllb.en2zh(text)


def zh_to_en(text: str) -> TranslateResult:
    # 整句中->英（写 metadata 用）：裸 NLLB 比 engine 的 en->中术语管线更干净。
    return TranslateResult(nllb.zh2en(text), "zh_to_en")


def en_to_zh(text: str) -> TranslateResult:
    return TranslateResult(_general(text, EN_LANG, ZH_LANG), "en_to_zh")


def translate(text: str, task: str = "fxname") -> TranslateResult:
    """task: fxname | zh_to_en | en_to_zh。"""
    if task == "fxname":
        return to_fxname(text)
    if task == "zh_to_en":
        return zh_to_en(text)
    if task == "en_to_zh":
        return en_to_zh(text)
    raise ValueError(f"unknown task: {task!r}")


if __name__ == "__main__":
    print("FXName :", to_fxname("奥古斯塔 A109 飞走 01").text)
    print("FXName :", to_fxname("玻璃杯清脆碰撞").text)
    print("zh->en :", zh_to_en("远处传来沉闷的雷声，伴随金属门缓缓关闭。").text)
    print("en->zh :", en_to_zh("Heavy metal door slam with reverberant tail.").text)
