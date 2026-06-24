"""NLLB-200 本地翻译推理引擎（CTranslate2 + transformers + 音频术语库）。"""



from __future__ import annotations



import re

from dataclasses import dataclass, field

from enum import Enum

from pathlib import Path

from typing import Any, Callable



import ctranslate2

import transformers



from glossary.filename_parser import looks_like_filename, translate_filename

from glossary.boom_style import BoomStyleIndex
from glossary.fx_name import sanitize_fx_fragment, validate_fx_name
from glossary.fx_slots import SlotTerm, assemble_fx_name, infer_slot, split_slot_terms
from glossary.matcher import GlossaryMatcher, GlossaryNotFoundError

from glossary.polish import polish_text
from glossary.zh_compose import compose_zh_to_en_debug



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

    debug: dict[str, Any] = field(default_factory=dict)



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

        self._boom_style: BoomStyleIndex | None = None



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

    def _boom_style_index(self) -> BoomStyleIndex:
        if self._boom_style is None:
            self._boom_style = BoomStyleIndex()
        return self._boom_style

    def _style_zh_fx_name(
        self, text: str, preserve_order: bool = False
    ) -> tuple[str, dict[str, Any]]:
        styled = self._boom_style_index().style_fx_name(
            text, preserve_order=preserve_order
        )
        return styled.text, {
            "boom_index_used": styled.boom_index_used,
            "boom_phrase_hits": styled.boom_phrase_hits,
            "selected_terms": styled.selected_terms,
        }

    def _hybrid_zh_fx_name(
        self, unknown_zh: list[str]
    ) -> tuple[list[SlotTerm], list[str]]:
        terms: list[SlotTerm] = []
        seen = set()
        candidate_fragments: list[str] = []
        for chunk in unknown_zh:
            if not chunk.strip():
                continue
            translated = self._nllb_translate(chunk, ZH_LANG, EN_LANG)
            fragment = sanitize_fx_fragment(polish_text(translated, tgt_is_zh=False))
            fragment, _boom_debug = self._style_zh_fx_name(fragment)
            if fragment:
                candidate_fragments.append(fragment)
            for token in fragment.split():
                if token.lower() not in seen:
                    terms.extend(
                        split_slot_terms(
                            token,
                            infer_slot(token),
                            source="fallback",
                        )
                    )
                    seen.add(token.lower())
        return terms, candidate_fragments



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
                composed, compose_debug = compose_zh_to_en_debug(text, self._glossary)
                glossary_hits = compose_debug.glossary_hits
                hybrid_used = False
                candidate_fragments: list[str] = []
                if glossary_hits >= 1:
                    coverage_ok = compose_debug.coverage >= 0.75
                    unknown_ok = not compose_debug.unknown_zh
                    slot_terms = list(compose_debug.slots)
                    if coverage_ok and unknown_ok:
                        fallback_terms: list[SlotTerm] = []
                    else:
                        fallback_terms, candidate_fragments = self._hybrid_zh_fx_name(
                            compose_debug.unknown_zh
                        )
                        slot_terms.extend(fallback_terms)
                        hybrid_used = True
                    assembly = assemble_fx_name(slot_terms)
                    translated = polish_text(assembly.text, tgt_is_zh=False)
                    translated, boom_debug = self._style_zh_fx_name(
                        translated, preserve_order=True
                    )
                    quality = validate_fx_name(text, translated)
                    return TranslationResult(
                        text=translated,
                        src_lang=src_lang,
                        tgt_lang=tgt_lang,
                        mode=resolved.value,
                        pro_mode=pro_mode,
                        glossary_hits=glossary_hits,
                        debug={
                            "coverage": round(compose_debug.coverage, 4),
                            "glossary_hits": glossary_hits,
                            "unknown_zh": compose_debug.unknown_zh,
                            "matched_terms": compose_debug.matched_terms,
                            "hybrid_fallback": hybrid_used,
                            "candidate_fragments": candidate_fragments,
                            **boom_debug,
                            "slots": assembly.slots,
                            "assembled_order": assembly.assembled_order,
                            "reorder_reason": assembly.reorder_reason,
                            "quality": quality.quality,
                            "issues": quality.issues,
                        },
                    )
                raw_translated = self._nllb_translate(text, src_lang, tgt_lang)
                translated = sanitize_fx_fragment(raw_translated)
                if not translated:
                    translated = polish_text(raw_translated, tgt_is_zh=False)
                candidate_fragments = [translated] if translated else []
                translated, boom_debug = self._style_zh_fx_name(translated)
                slot_terms = [
                    term
                    for token in translated.split()
                    for term in split_slot_terms(token, infer_slot(token), source="fallback")
                ]
                assembly = assemble_fx_name(slot_terms)
                translated = assembly.text
                quality = validate_fx_name(text, translated)
                return TranslationResult(
                    text=translated,
                    src_lang=src_lang,
                    tgt_lang=tgt_lang,
                    mode=resolved.value,
                    pro_mode=pro_mode,
                    glossary_hits=0,
                    debug={
                        "coverage": round(compose_debug.coverage, 4),
                        "glossary_hits": 0,
                        "unknown_zh": compose_debug.unknown_zh,
                        "matched_terms": compose_debug.matched_terms,
                        "hybrid_fallback": True,
                        "candidate_fragments": candidate_fragments,
                        **boom_debug,
                        "slots": assembly.slots,
                        "assembled_order": assembly.assembled_order,
                        "reorder_reason": assembly.reorder_reason,
                        "quality": quality.quality,
                        "issues": quality.issues,
                    },
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


