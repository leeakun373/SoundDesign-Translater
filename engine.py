"""NLLB-200 本地翻译推理引擎（CTranslate2 + transformers + 音频术语库）。"""



from __future__ import annotations



import re

from dataclasses import dataclass

from enum import Enum

from pathlib import Path

from typing import Callable



import ctranslate2

import transformers



from glossary.filename_parser import looks_like_filename, translate_filename

from glossary.matcher import GlossaryMatcher, GlossaryNotFoundError

from glossary.polish import polish_text
from glossary.zh_compose import compose_zh_to_en



MODEL_DIR = Path(__file__).parent / "nllb_int8_model"

ZH_LANG = "zho_Hans"

EN_LANG = "eng_Latn"



LANG_LABELS = {ZH_LANG: "中", EN_LANG: "英"}

MODE_LABELS = {"auto": "自动", "sentence": "句子", "filename": "文件名"}





class TranslateMode(str, Enum):

    AUTO = "auto"

    SENTENCE = "sentence"

    FILENAME = "filename"





@dataclass(frozen=True)

class TranslationResult:

    text: str

    src_lang: str

    tgt_lang: str

    mode: str = "sentence"

    pro_mode: bool = True

    glossary_hits: int = 0



    @property

    def direction_label(self) -> str:

        return f"{LANG_LABELS[self.src_lang]} → {LANG_LABELS[self.tgt_lang]}"



    @property

    def status_label(self) -> str:

        pro = "专业开" if self.pro_mode else "专业关"

        return (

            f"{MODE_LABELS.get(self.mode, self.mode)} · {self.direction_label} · "

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





class NllbTranslator:

    """封装 NLLB-200 int8 模型的加载与中英互译推理。"""



    def __init__(self) -> None:

        self._translator: ctranslate2.Translator | None = None

        self._tokenizer: transformers.PreTrainedTokenizer | None = None

        self._glossary: GlossaryMatcher | None = None

        self._glossary_error: str | None = None



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

            self._glossary_error = None

        except GlossaryNotFoundError as exc:

            self._glossary = None

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



    def translate(

        self,

        text: str,

        src_lang: str | None = None,

        tgt_lang: str | None = None,

        mode: TranslateMode | str = TranslateMode.AUTO,

        pro_mode: bool = True,

    ) -> TranslationResult:

        if isinstance(mode, str):

            mode = TranslateMode(mode)



        if not text.strip():

            src, tgt = detect_lang_pair(text)

            return TranslationResult(

                text="", src_lang=src, tgt_lang=tgt, mode=mode.value, pro_mode=pro_mode

            )



        if not self._translator or not self._tokenizer:

            raise TranslationError("翻译引擎未就绪")



        if src_lang is None or tgt_lang is None:

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

                    pro_mode=pro_mode,

                    glossary_hits=glossary_hits,

                )



            if not pro_mode or not self._glossary:

                translated = self._nllb_translate(text, src_lang, tgt_lang)

                translated = polish_text(translated, tgt_is_zh=to_zh)

                return TranslationResult(

                    text=translated,

                    src_lang=src_lang,

                    tgt_lang=tgt_lang,

                    mode=resolved.value,

                    pro_mode=pro_mode,

                )



            src_is_zh = src_lang == ZH_LANG

            if src_is_zh and pro_mode and self._glossary and resolved == TranslateMode.SENTENCE:
                composed, glossary_hits = compose_zh_to_en(text, self._glossary)
                if glossary_hits >= 1:
                    translated = polish_text(composed, tgt_is_zh=False)
                    return TranslationResult(
                        text=translated,
                        src_lang=src_lang,
                        tgt_lang=tgt_lang,
                        mode=resolved.value,
                        pro_mode=pro_mode,
                        glossary_hits=glossary_hits,
                    )
                translated = self._nllb_translate(text, src_lang, tgt_lang)
                translated = polish_text(translated, tgt_is_zh=False)
                return TranslationResult(
                    text=translated,
                    src_lang=src_lang,
                    tgt_lang=tgt_lang,
                    mode=resolved.value,
                    pro_mode=pro_mode,
                    glossary_hits=0,
                )

            segments, glossary_hits = self._glossary.segment_for_translation(

                text, src_is_zh

            )

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

                pro_mode=pro_mode,

                glossary_hits=glossary_hits,

            )

        except TranslationError:

            raise

        except Exception as exc:

            raise TranslationError(f"推理失败: {exc}") from exc


