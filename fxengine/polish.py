"""Stable FXName Polish stub; intentionally separate from Normalize."""

from __future__ import annotations

from fxengine.models import PolishResult


class FXNamePolisher:
    def polish(self, input_text: str) -> PolishResult:
        return PolishResult(
            input_text=input_text,
            output_fxname="",
            quality="needs_review",
            issues=["stub"],
            debug={"stub": True},
        )
