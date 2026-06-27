"""Stable example-retrieval stub for the v0.3 scaffold."""

from __future__ import annotations

from fxengine.models import ExampleRetrievalResult


class ExampleRetriever:
    def retrieve(self, query: str, limit: int = 5) -> ExampleRetrievalResult:
        return ExampleRetrievalResult(
            query=query,
            examples=[],
            quality="needs_review",
            issues=["stub"],
            debug={"stub": True, "limit": limit},
        )
