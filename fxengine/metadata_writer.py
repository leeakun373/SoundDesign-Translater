"""Stable Metadata Description stub for the v0.3 scaffold."""

from __future__ import annotations

from fxengine.models import FXToken, MetadataResult


class MetadataWriter:
    def write(
        self,
        input_text: str,
        source_tokens: list[FXToken] | None = None,
        references: list[str] | None = None,
    ) -> MetadataResult:
        return MetadataResult(
            input_text=input_text,
            description="",
            quality="needs_review",
            issues=["stub"],
            source_tokens=list(source_tokens or []),
            references=list(references or []),
            debug={"stub": True},
        )
