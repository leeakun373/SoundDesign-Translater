"""Default FXName Normalize facade."""

from __future__ import annotations

import re
from dataclasses import replace

from glossary.fx_name import strip_unsafe_fx_phrases, unsafe_fx_word_indices
from glossary.fx_slots import SlotTerm, assemble_fx_name, infer_slot, split_slot_terms
from glossary.zh_normalize import normalize_fxname_input

from fxengine.canonical_db import CanonicalDB, CanonicalMatch, title_fx_text
from fxengine.models import TOKEN_REVIEW_SCHEMA_VERSION, FXNameResult, FXToken
from fxengine.personal_dictionary import PersonalDictionary, PersonalEntry
from fxengine.preferences import FXPreferences
from fxengine.scorer import BoomScorer
from fxengine.tokenizer import FXTokenizer, RawToken


COMMON_FX_TOKENS = frozenset(
    {
        "whoosh",
        "impact",
        "hit",
        "scrape",
        "rattle",
        "creak",
        "crack",
        "blast",
        "explosion",
        "tail",
        "long",
        "short",
        "close",
        "far",
    }
)
ONOMATOPOEIA_TOKENS = frozenset({"kuang", "duang", "zila", "kacha", "peng"})
TECHNICAL_EXACT_TOKENS = frozenset({"MS", "AB"})
TECHNICAL_TOKEN_RE = re.compile(
    r"^(?:[A-Za-z]{1,8}\d[A-Za-z0-9]*|\d+(?:\.\d+)?[kK]|\d+)$"
)


class FXNameNormalizer:
    """Deterministic canonical normalization with no NLLB dependency."""

    def __init__(
        self,
        canonical_db: CanonicalDB | None = None,
        personal_dictionary: PersonalDictionary | None = None,
        preferences: FXPreferences | None = None,
        scorer: BoomScorer | None = None,
        tokenizer: FXTokenizer | None = None,
    ) -> None:
        self.canonical_db = canonical_db or CanonicalDB()
        self.personal_dictionary = personal_dictionary or PersonalDictionary()
        self.preferences = preferences or FXPreferences()
        self.scorer = scorer or BoomScorer()
        self.tokenizer = tokenizer or FXTokenizer()

    def normalize(
        self, input_text: str, preferences: FXPreferences | None = None
    ) -> FXNameResult:
        prefs = preferences or self.preferences
        tokens: list[FXToken] = []
        metadata_candidates: list[str] = []
        raw_tokens = self.tokenizer.tokenize(input_text)
        unsafe_positions, input_rejected_fragments = self._unsafe_ascii_positions(raw_tokens)

        for index, raw_token in enumerate(raw_tokens):
            if index in unsafe_positions:
                tokens.append(
                    FXToken(
                        raw=raw_token.raw,
                        text="",
                        canonical=None,
                        slot="unknown",
                        source="pollution_filter",
                        confidence=1.0,
                        status="rejected",
                        issues=["unsafe_fragment_rejected"],
                        decision="ignored_pollution",
                    )
                )
                continue
            if raw_token.kind == "distance":
                tokens.append(self._distance_token(raw_token, prefs, metadata_candidates))
            elif raw_token.kind == "ascii":
                tokens.append(
                    self._resolve_ascii(raw_token, prefs, metadata_candidates)
                )
            else:
                tokens.extend(self._resolve_chinese(raw_token))

        output_tokens = [token for token in tokens if token.status in {"ok", "needs_review"} and token.text]
        assembled = self._assemble(output_tokens, prefs)
        output, output_rejected_fragments = strip_unsafe_fx_phrases(assembled.text)
        tokens = _mark_final_contributions(tokens, output)
        rejected_fragments = list(input_rejected_fragments)
        for fragment in output_rejected_fragments:
            if fragment not in rejected_fragments:
                rejected_fragments.append(fragment)

        issues: list[str] = []
        unknowns: list[str] = []
        for token in tokens:
            for issue in token.issues:
                label = (
                    f"{issue}:{token.raw}"
                    if issue.startswith("unknown_")
                    or issue in {"distance_excluded", "technical_token_excluded"}
                    else issue
                )
                if label not in issues:
                    issues.append(label)
            if any(issue.startswith("unknown_") for issue in token.issues):
                unknowns.append(token.raw)
        if rejected_fragments:
            issues.append("unsafe_fragment_rejected")
        if input_text.strip() and not output and not unknowns:
            issues.append("empty_output")

        boom = self.scorer.score(output) if output else self.scorer.score("")
        suggestions = [boom.suggestion] if boom.suggestion and boom.suggestion != output else []
        quality = "fail" if "empty_output" in issues else "needs_review" if issues else "pass"
        unknown_zh = [token.raw for token in tokens if "unknown_zh" in token.issues]
        unknown_ascii = [token.raw for token in tokens if "unknown_ascii" in token.issues]

        return FXNameResult(
            input_text=input_text,
            output_fxname=output,
            mode="normalize",
            tokens=tokens,
            quality=quality,
            issues=issues,
            unknowns=unknowns,
            suggestions=suggestions,
            boom_confidence=boom.confidence,
            boom_suggestion=boom.suggestion,
            debug={
                "token_review_schema_version": TOKEN_REVIEW_SCHEMA_VERSION,
                "normalization_mode": "normalize",
                "normalized_input": normalize_fxname_input(input_text),
                "preserve_order": prefs.preserve_order,
                "preferences": {
                    "name": prefs.name,
                    "allow_distance_in_fxname": prefs.allow_distance_in_fxname,
                    "boom_can_reorder": prefs.boom_can_reorder,
                    "boom_suggestion_only": prefs.boom_suggestion_only,
                    "strict_review": prefs.strict_review,
                    "keep_unknown_ascii": prefs.keep_unknown_ascii,
                },
                "metadata_candidates": metadata_candidates,
                "rejected_unsafe_fragments": rejected_fragments,
                "unknown_zh": unknown_zh,
                "unknown_ascii": unknown_ascii,
                "unknown_policy": (
                    "keep_raw_review" if prefs.keep_unknown_ascii else "review"
                ),
                "nllb_fallback_used": False,
                "boom_index_used": boom.available,
                "boom_phrase_hits": boom.phrase_hits,
                "boom_reorder_suppressed": not prefs.boom_can_reorder,
                "assembled_order": assembled.assembled_order,
                "reorder_reason": assembled.reorder_reason,
                "glossary_hits": sum(
                    token.source in {"canonical_csv", "glossary_fallback"}
                    for token in tokens
                ),
            },
        )

    @staticmethod
    def _unsafe_ascii_positions(
        raw_tokens: list[RawToken],
    ) -> tuple[set[int], list[str]]:
        """Reject chat phrases before unknown-token handling can split them apart."""
        removed: set[int] = set()
        rejected: list[str] = []
        start = 0
        while start < len(raw_tokens):
            if raw_tokens[start].kind != "ascii":
                start += 1
                continue
            end = start
            while end < len(raw_tokens) and raw_tokens[end].kind == "ascii":
                end += 1
            words = [token.raw for token in raw_tokens[start:end]]
            local_removed, local_rejected = unsafe_fx_word_indices(words)
            removed.update(start + index for index in local_removed)
            for fragment in local_rejected:
                if fragment not in rejected:
                    rejected.append(fragment)
            start = end
        return removed, rejected

    def _resolve_ascii(
        self,
        raw_token: RawToken,
        prefs: FXPreferences,
        metadata_candidates: list[str],
    ) -> FXToken:
        personal = self.personal_dictionary.resolve_entry(raw_token.raw)
        if personal:
            return self._personal_token(raw_token.raw, personal)
        if _is_technical_token(raw_token.raw):
            metadata_candidates.append(raw_token.raw)
            return FXToken(
                raw=raw_token.raw,
                text="",
                canonical=None,
                slot="detail",
                source="technical_token_rule",
                confidence=1.0,
                status="ignored",
                issues=["technical_token_excluded"],
                decision="metadata_candidate",
                metadata_candidate=True,
            )
        match = self.canonical_db.resolve_ascii(raw_token.raw)
        if match.status == "unknown" and raw_token.raw.casefold() in COMMON_FX_TOKENS:
            canonical = title_fx_text(raw_token.raw)
            return FXToken(
                raw=raw_token.raw,
                text=canonical,
                canonical=canonical,
                slot=infer_slot(canonical),
                source="keep_raw_rule",
                confidence=0.9,
                status="ok",
                issues=[],
                decision="kept_raw",
            )
        if match.status == "unknown" and prefs.keep_unknown_ascii:
            if raw_token.raw.casefold() in ONOMATOPOEIA_TOKENS:
                return _match_to_token(match)
            canonical = title_fx_text(raw_token.raw)
            return FXToken(
                raw=raw_token.raw,
                text=canonical,
                canonical=canonical,
                slot="unknown",
                source="keep_raw_rule",
                confidence=0.25,
                status="needs_review",
                issues=["unknown_ascii"],
                decision="kept_raw",
            )
        return _match_to_token(match)

    def _resolve_chinese(self, raw_token: RawToken) -> list[FXToken]:
        personal = self.personal_dictionary.resolve_entry(raw_token.raw)
        if personal:
            return [self._personal_token(raw_token.raw, personal)]

        personal_entries = sorted(
            (
                entry
                for entry in self.personal_dictionary.entries()
                if entry.alias and any("\u4e00" <= char <= "\u9fff" for char in entry.alias)
            ),
            key=lambda entry: len(entry.alias),
            reverse=True,
        )
        if not personal_entries:
            return [
                _match_to_token(match)
                for match in self.canonical_db.segment_chinese(raw_token.raw)
            ]

        out: list[FXToken] = []
        unmatched: list[str] = []

        def flush_unmatched() -> None:
            if not unmatched:
                return
            text = "".join(unmatched)
            out.extend(
                _match_to_token(match) for match in self.canonical_db.segment_chinese(text)
            )
            unmatched.clear()

        position = 0
        while position < len(raw_token.raw):
            entry = next(
                (
                    candidate
                    for candidate in personal_entries
                    if raw_token.raw.startswith(candidate.alias, position)
                ),
                None,
            )
            if entry is None:
                unmatched.append(raw_token.raw[position])
                position += 1
                continue
            flush_unmatched()
            out.append(self._personal_token(entry.alias, entry))
            position += len(entry.alias)
        flush_unmatched()
        return out

    @staticmethod
    def _personal_token(raw: str, entry: PersonalEntry) -> FXToken:
        if entry.action == "ignore":
            return FXToken(
                raw,
                "",
                None,
                "ignored",
                "personal_dictionary",
                1.0,
                "ignored",
                [],
                "ignored_personal",
            )
        canonical = title_fx_text(entry.canonical or raw)
        return FXToken(
            raw=raw,
            text=canonical,
            canonical=canonical,
            slot=infer_slot(canonical),
            source="personal_dictionary",
            confidence=1.0,
            status="ok",
            issues=[],
            decision=("kept_raw" if entry.action == "keep" else "mapped_personal"),
        )

    @staticmethod
    def _distance_token(
        raw_token: RawToken,
        prefs: FXPreferences,
        metadata_candidates: list[str],
    ) -> FXToken:
        if prefs.allow_distance_in_fxname:
            return FXToken(
                raw_token.raw,
                raw_token.raw.lower(),
                raw_token.raw.lower(),
                "detail",
                "distance_rule",
                1.0,
                "ok",
                [],
                "kept_raw",
            )
        metadata_candidates.append(raw_token.raw.lower())
        return FXToken(
            raw_token.raw,
            "",
            None,
            "detail",
            "distance_rule",
            1.0,
            "ignored",
            ["distance_excluded"],
            "metadata_candidate",
            False,
            True,
        )

    @staticmethod
    def _assemble(tokens: list[FXToken], prefs: FXPreferences):
        slot_terms: list[SlotTerm] = []
        for group, token in enumerate(tokens):
            if token.source == "distance_rule":
                slot_terms.append(SlotTerm(token.text, token.slot, token.source, group))
            else:
                slot_terms.extend(
                    split_slot_terms(token.text, token.slot, source=token.source, group=group)
                )
        return assemble_fx_name(slot_terms, preserve_order=prefs.preserve_order)


def normalize_fxname(
    input_text: str,
    *,
    normalizer: FXNameNormalizer | None = None,
    preferences: FXPreferences | None = None,
) -> FXNameResult:
    """Convenience facade for callers that do not need dependency injection."""
    return (normalizer or FXNameNormalizer()).normalize(input_text, preferences)


def _match_to_token(match: CanonicalMatch) -> FXToken:
    if match.status == "unknown":
        source = "unknown_review"
        decision = "unknown"
    elif match.status == "ignored":
        source = "pollution_filter"
        decision = "ignored_pollution"
    elif match.source == "canonical_csv":
        source = "canonical_csv"
        decision = "mapped_canonical"
    else:
        source = "glossary_fallback"
        decision = "mapped_glossary"
    return FXToken(
        raw=match.raw,
        text=match.canonical or "",
        canonical=match.canonical,
        slot=match.slot,
        source=source,
        confidence=1.0 if match.status in {"ok", "ignored"} else 0.0,
        status=match.status,
        issues=list(match.issues),
        decision=decision,
    )


def _is_technical_token(raw: str) -> bool:
    return raw.upper() in TECHNICAL_EXACT_TOKENS or bool(
        TECHNICAL_TOKEN_RE.fullmatch(raw)
    )


def _mark_final_contributions(tokens: list[FXToken], output: str) -> list[FXToken]:
    final_words = output.casefold().split()
    seen_groups: set[tuple[str, ...]] = set()
    marked: list[FXToken] = []
    for token in tokens:
        group = tuple(token.text.casefold().split())
        eligible = token.decision in {
            "mapped_personal",
            "mapped_canonical",
            "mapped_glossary",
            "kept_raw",
        }
        contributes = bool(
            eligible
            and group
            and group not in seen_groups
            and _contains_word_sequence(final_words, group)
        )
        if contributes:
            seen_groups.add(group)
        marked.append(replace(token, contributes_to_fxname=contributes))
    return marked


def _contains_word_sequence(words: list[str], sequence: tuple[str, ...]) -> bool:
    width = len(sequence)
    return any(tuple(words[start : start + width]) == sequence for start in range(len(words)))
