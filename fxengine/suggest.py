"""Stable FXName Suggest stub; intentionally separate from Normalize."""

from __future__ import annotations

from fxengine.models import SuggestionResult


class FXNameSuggester:
    def suggest(self, input_text: str, limit: int = 3) -> SuggestionResult:
        return SuggestionResult(
            input_text=input_text,
            candidates=[],
            quality="needs_review",
            issues=["stub"],
            debug={"stub": True, "limit": limit},
        )
