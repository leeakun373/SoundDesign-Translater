"""NLLB 推理薄封装：复用 engine.py 的 NllbTranslator，懒加载单例 + 结果缓存。"""

from __future__ import annotations

from functools import lru_cache

from engine import EN_LANG, ZH_LANG, NllbTranslator

_translator: NllbTranslator | None = None


def _engine() -> NllbTranslator:
    global _translator
    if _translator is None:
        inst = NllbTranslator()
        inst.load()
        _translator = inst
    return _translator


def is_available() -> bool:
    try:
        return _engine().is_ready
    except Exception:
        return False


@lru_cache(maxsize=50000)
def zh2en(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    return _engine()._nllb_translate(text, ZH_LANG, EN_LANG).strip()


@lru_cache(maxsize=50000)
def en2zh(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    return _engine()._nllb_translate(text, EN_LANG, ZH_LANG).strip()
