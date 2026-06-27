"""NLLB-200 本地翻译推理引擎（CTranslate2 + transformers + 音频术语库）。"""



from __future__ import annotations



import re

from dataclasses import dataclass, field

from enum import Enum

from pathlib import Path

from typing import Any, Callable



import ctranslate2

import transformers



from fxengine.canonical_db import CanonicalDB
from fxengine.diagnostics import result_to_debug
from fxengine.normalizer import FXNameNormalizer
from fxengine.scorer import BoomScorer
from glossary.filename_parser import looks_like_filename, translate_filename
from glossary.boom_style import BoomStyleIndex
from glossary.matcher import GlossaryMatcher, GlossaryNotFoundError
from glossary.polish import polish_text



MODEL_DIR = Path(__file__).parent / "nllb_int8_model"

ZH_LANG = "zho_Hans"

EN_LANG = "eng_Latn"



LANG_LABELS = {ZH_LANG: "中", EN_LANG: "英"}

MODE_LABELS = {"auto": "自动", "sentence": "句子", "filename": "文件名", "fxname": "FX命名"}

TASK_MODE_LABELS = {"general": "普通翻译", "fxname": "音效命名"}





class TranslateMode(str, Enum):

    AUTO = "auto"

    SENTENCE = "sentence"

    FILENAME = "filename"

    FXNAME = "fxname"





class TaskMode(str, Enum):

    GENERAL = "general"

    FXNAME = "fxname"





@dataclass(frozen=True)

class TranslationResult:

    text: str

    src_lang: str

    tgt_lang: str

    mode: str = "sentence"

    task_mode: str = "fxname"

    pro_mode: bool = True

    glossary_hits: int = 0

    debug: dict[str, Any] = field(default_factory=dict)



    @property

    def direction_label(self) -> str:

        return f"{LANG_LABELS[self.src_lang]} → {LANG_LABELS[self.tgt_lang]}"



    @property

    def status_label(self) -> str:

        pro = "专业开" if self.pro_mode else "专业关"
        task = TASK_MODE_LABELS.get(self.task_mode, self.task_mode)

        return (

            f"{task} · {MODE_LABELS.get(self.mode, self.mode)} · {self.direction_label} · "

            f"{pro} · 术语命中 {self.glossary_hits}"

        )





class ModelNotFoundError(Exception):

    """模型目录不存在或加载失败。"""





class TranslationError(Exception):

    """翻译推理失败或引擎未就绪。"""





def detect_device() -> str:

    return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"





def detect_lang_pair(text: str) -> tuple[str, str]:
    cjk_count = len(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", text))
    latin_count = len(re.findall(r"[A-Za-z]", text))
    # 混合 FX 描述（中文为主 + 夹英文词）→ 中→英组装
    if cjk_count >= 2 and latin_count > 0 and cjk_count >= latin_count * 0.35:
        return ZH_LANG, EN_LANG
    if cjk_count > latin_count:
        return ZH_LANG, EN_LANG
    if latin_count > cjk_count:
        return EN_LANG, ZH_LANG
    if cjk_count > 0:
        return ZH_LANG, EN_LANG
    return EN_LANG, ZH_LANG


def detect_lang_pair_fxname(text: str) -> tuple[str, str]:
    """FXName mode: any CJK + ASCII mix → zh→en naming pipeline."""
    cjk_count = len(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", text))
    latin_count = len(re.findall(r"[A-Za-z]", text))
    if cjk_count > 0:
        return ZH_LANG, EN_LANG
    if latin_count > 0:
        return EN_LANG, EN_LANG
    return detect_lang_pair(text)





class NllbTranslator:

    """封装 NLLB-200 int8 模型的加载与中英互译推理。"""



    def __init__(self) -> None:

        self._translator: ctranslate2.Translator | None = None

        self._tokenizer: transformers.PreTrainedTokenizer | None = None

        self._glossary: GlossaryMatcher | None = None

        self._glossary_error: str | None = None

        self._boom_style: BoomStyleIndex | None = None

        self._fxname_normalizer: FXNameNormalizer | None = None



    @property

    def is_ready(self) -> bool:

        return self._translator is not None and self._tokenizer is not None



    @property

    def glossary_ready(self) -> bool:

        return self._glossary is not None



    @property

    def glossary_error(self) -> str | None:

        return self._glossary_error



    def load_glossary(self) -> None:

        try:

            self._glossary = GlossaryMatcher()

            self._fxname_normalizer = None

            self._glossary_error = None

        except GlossaryNotFoundError as exc:

            self._glossary = None

            self._fxname_normalizer = None

            self._glossary_error = str(exc)



    def load(self, on_progress: Callable[[str], None] | None = None) -> None:

        self.load_glossary()

        if on_progress:

            on_progress("正在检查模型目录...")

        if not MODEL_DIR.exists() or not any(MODEL_DIR.iterdir()):

            raise ModelNotFoundError(

                f"未找到模型文件，请确保目录存在且不为空: {MODEL_DIR}"

            )

        if on_progress:

            on_progress("正在加载本地模型...")

        try:

            device = detect_device()

            self._tokenizer = transformers.AutoTokenizer.from_pretrained(str(MODEL_DIR))

            self._translator = ctranslate2.Translator(

                str(MODEL_DIR), device=device, compute_type="int8"

            )

            if on_progress:

                on_progress(f"模型加载完毕 ({device})")

        except ModelNotFoundError:

            raise

        except Exception as exc:

            raise ModelNotFoundError(f"模型加载底层错误: {exc}") from exc



    def _resolve_mode(self, text: str, mode: TranslateMode) -> TranslateMode:

        if mode != TranslateMode.AUTO:

            return mode

        if self._glossary and looks_like_filename(text, self._glossary):

            return TranslateMode.FILENAME

        return TranslateMode.SENTENCE

    def _nllb_translate(self, text: str, src_lang: str, tgt_lang: str) -> str:

        if not self._translator or not self._tokenizer:

            raise TranslationError("翻译引擎未就绪")

        self._tokenizer.src_lang = src_lang

        source_ids = self._tokenizer.encode(text)

        source_tokens = self._tokenizer.convert_ids_to_tokens(source_ids)

        results = self._translator.translate_batch(

            [source_tokens], target_prefix=[[tgt_lang]]

        )

        output_tokens = results[0].hypotheses[0]

        if output_tokens and output_tokens[0] == tgt_lang:

            output_tokens = output_tokens[1:]

        output_ids = self._tokenizer.convert_tokens_to_ids(output_tokens)

        return self._tokenizer.decode(output_ids, skip_special_tokens=True)

    def _boom_style_index(self) -> BoomStyleIndex:
        if self._boom_style is None:
            self._boom_style = BoomStyleIndex()
        return self._boom_style

    def _fxname_normalizer_facade(self) -> FXNameNormalizer:
        if self._fxname_normalizer is None:
            if self._glossary is None:
                raise TranslationError(
                    "FXName Normalize requires professional mode and a loaded glossary"
                )
            self._fxname_normalizer = FXNameNormalizer(
                canonical_db=CanonicalDB(self._glossary),
                scorer=BoomScorer(self._boom_style_index()),
            )
        return self._fxname_normalizer

    @staticmethod
    def _should_use_fxname_pipeline(
        *,
        task_mode: TaskMode,
        mode: TranslateMode,
        src_lang: str,
        tgt_lang: str,
        pro_mode: bool,
        glossary_ready: bool,
        resolved_mode: TranslateMode,
    ) -> bool:
        if not (pro_mode and glossary_ready and tgt_lang == EN_LANG):
            return False
        if task_mode == TaskMode.FXNAME:
            return resolved_mode in (TranslateMode.SENTENCE, TranslateMode.FXNAME, TranslateMode.AUTO)
        if mode == TranslateMode.FXNAME:
            return True
        return False

    def _translate_zh_fxname(
        self,
        text: str,
        src_lang: str,
        tgt_lang: str,
        resolved: TranslateMode,
        pro_mode: bool,
    ) -> TranslationResult:
        normalized = self._fxname_normalizer_facade().normalize(text)
        debug = result_to_debug(normalized)
        compatibility_issues = list(normalized.issues)
        if normalized.debug.get("unknown_zh") and "unknown_zh" not in compatibility_issues:
            compatibility_issues.append("unknown_zh")
        debug.update(
            {
                "task_mode": TaskMode.FXNAME.value,
                "issues": compatibility_issues,
                "hybrid_fallback": False,
                "candidate_fragments": [],
                "rejected_candidates": [],
                "selected_terms": normalized.output_fxname.split(),
                "slots": [
                    {
                        "token": token.text,
                        "slot": token.slot,
                        "source": token.source,
                    }
                    for token in normalized.tokens
                    if token.text
                ],
                "structural_quality": normalized.quality,
                "structural_issues": compatibility_issues,
                "matched_bad_phrases": [],
            }
        )
        return TranslationResult(
            text=normalized.output_fxname,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            mode=resolved.value,
            task_mode=TaskMode.FXNAME.value,
            pro_mode=pro_mode,
            glossary_hits=int(normalized.debug.get("glossary_hits", 0)),
            debug=debug,
        )

    def _translate_glossary_segments(
        self,
        text: str,
        src_lang: str,
        tgt_lang: str,
        resolved: TranslateMode,
        task_mode: TaskMode,
        pro_mode: bool,
    ) -> TranslationResult:
        src_is_zh = src_lang == ZH_LANG
        to_zh = tgt_lang == ZH_LANG
        segments, glossary_hits = self._glossary.segment_for_translation(text, src_is_zh)
        parts: list[str] = []
        for segment in segments:
            if segment.entry:
                parts.append(segment.entry.zh if to_zh else segment.entry.en)
            elif segment.text.strip():
                parts.append(self._nllb_translate(segment.text, src_lang, tgt_lang))
            else:
                parts.append(segment.text)
        joiner = "" if to_zh else " "
        translated = joiner.join(parts)
        if to_zh:
            translated, extra = self._glossary.force_replace_en_to_zh(translated)
            glossary_hits += extra
        translated = polish_text(translated, tgt_is_zh=to_zh)
        return TranslationResult(
            text=translated,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            mode=resolved.value,
            task_mode=task_mode.value,
            pro_mode=pro_mode,
            glossary_hits=glossary_hits,
            debug={"task_mode": task_mode.value},
        )

    def translate_fxname(
        self,
        text: str,
        src_lang: str | None = None,
        tgt_lang: str | None = None,
        mode: TranslateMode | str = TranslateMode.AUTO,
        pro_mode: bool = True,
    ) -> TranslationResult:
        """FXName / 音效命名专用入口；中→英走 compose/slot 管线，不直接信任整句 NLLB。"""
        return self.translate(
            text,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            mode=mode,
            pro_mode=pro_mode,
            task_mode=TaskMode.FXNAME,
        )

    def translate_general(
        self,
        text: str,
        src_lang: str | None = None,
        tgt_lang: str | None = None,
        mode: TranslateMode | str = TranslateMode.AUTO,
        pro_mode: bool = True,
    ) -> TranslationResult:
        """General / 普通翻译：句子走术语分段 + NLLB，不把 FXName 管线当 gold。"""
        return self.translate(
            text,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            mode=mode,
            pro_mode=pro_mode,
            task_mode=TaskMode.GENERAL,
        )

    def translate(

        self,

        text: str,

        src_lang: str | None = None,

        tgt_lang: str | None = None,

        mode: TranslateMode | str = TranslateMode.AUTO,

        pro_mode: bool = True,

        task_mode: TaskMode | str = TaskMode.FXNAME,

    ) -> TranslationResult:

        if isinstance(mode, str):

            mode = TranslateMode(mode)

        if isinstance(task_mode, str):

            task_mode = TaskMode(task_mode)



        if not text.strip():

            src, tgt = detect_lang_pair(text)

            return TranslationResult(

                text="", src_lang=src, tgt_lang=tgt, mode=mode.value, task_mode=task_mode.value, pro_mode=pro_mode

            )



        if not self._translator or not self._tokenizer:

            raise TranslationError("翻译引擎未就绪")



        if src_lang is None or tgt_lang is None:
            if task_mode == TaskMode.FXNAME or mode == TranslateMode.FXNAME:
                src_lang, tgt_lang = detect_lang_pair_fxname(text)
            else:
                src_lang, tgt_lang = detect_lang_pair(text)

        resolved = self._resolve_mode(text, mode)

        to_zh = tgt_lang == ZH_LANG

        glossary_hits = 0



        try:

            if resolved == TranslateMode.FILENAME and pro_mode and self._glossary:



                def _nllb_segment(segment: str) -> str:

                    if not segment.strip():

                        return segment

                    return self._nllb_translate(segment, src_lang, tgt_lang)



                result_text, glossary_hits = translate_filename(

                    text, self._glossary, _nllb_segment, to_zh=to_zh

                )

                result_text = polish_text(result_text, tgt_is_zh=to_zh)

                return TranslationResult(

                    text=result_text,

                    src_lang=src_lang,

                    tgt_lang=tgt_lang,

                    mode=resolved.value,

                    task_mode=task_mode.value,

                    pro_mode=pro_mode,

                    glossary_hits=glossary_hits,

                    debug={"task_mode": task_mode.value},

                )



            fx_normalize_requested = (
                task_mode == TaskMode.FXNAME or mode == TranslateMode.FXNAME
            ) and tgt_lang == EN_LANG
            if fx_normalize_requested and (not pro_mode or not self._glossary):
                raise TranslationError(
                    "FXName Normalize requires professional mode and a loaded glossary"
                )

            if not pro_mode or not self._glossary:

                translated = self._nllb_translate(text, src_lang, tgt_lang)

                translated = polish_text(translated, tgt_is_zh=to_zh)

                return TranslationResult(

                    text=translated,

                    src_lang=src_lang,

                    tgt_lang=tgt_lang,

                    mode=resolved.value,

                    task_mode=task_mode.value,

                    pro_mode=pro_mode,

                    debug={"task_mode": task_mode.value},

                )



            if self._should_use_fxname_pipeline(
                task_mode=task_mode,
                mode=mode,
                src_lang=src_lang,
                tgt_lang=tgt_lang,
                pro_mode=pro_mode,
                glossary_ready=self._glossary is not None,
                resolved_mode=resolved,
            ):
                return self._translate_zh_fxname(
                    text, src_lang, tgt_lang, resolved, pro_mode
                )

            return self._translate_glossary_segments(
                text, src_lang, tgt_lang, resolved, task_mode, pro_mode
            )

        except TranslationError:

            raise

        except Exception as exc:

            raise TranslationError(f"推理失败: {exc}") from exc


