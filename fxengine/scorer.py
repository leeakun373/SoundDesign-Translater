"""BOOM confidence/suggestion adapter that never replaces final Normalize output."""

from __future__ import annotations

from glossary.boom_style import BoomStyleIndex

from fxengine.models import BoomScoreResult


class BoomScorer:
    def __init__(self, index: BoomStyleIndex | None = None) -> None:
        self.index = index or BoomStyleIndex()

    def score(self, text: str) -> BoomScoreResult:
        styled = self.index.style_fx_name(text, preserve_order=True)
        denominator = max(1, len(styled.selected_terms) - 1)
        confidence = (
            round(min(1.0, len(styled.boom_phrase_hits) / denominator), 4)
            if styled.boom_index_used
            else None
        )
        return BoomScoreResult(
            input_text=text,
            confidence=confidence,
            suggestion=styled.suggested_text,
            phrase_hits=styled.boom_phrase_hits,
            available=styled.boom_index_used,
            debug={"final_text_unchanged": styled.text == text},
        )
