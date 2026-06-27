"""Stable structured results shared by FXName Engine modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FXToken:
    raw: str
    text: str
    canonical: str | None
    slot: str
    source: str
    confidence: float
    status: str
    issues: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FXNameResult:
    input_text: str
    output_fxname: str
    mode: str
    tokens: list[FXToken]
    quality: str
    issues: list[str]
    unknowns: list[str]
    suggestions: list[str]
    boom_confidence: float | None
    boom_suggestion: str | None
    debug: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MetadataResult:
    input_text: str
    description: str
    quality: str
    issues: list[str]
    source_tokens: list[FXToken]
    references: list[str]
    debug: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExampleRetrievalResult:
    query: str
    examples: list[str]
    quality: str
    issues: list[str]
    debug: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BoomScoreResult:
    input_text: str
    confidence: float | None
    suggestion: str | None
    phrase_hits: list[str]
    available: bool
    debug: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolishResult:
    input_text: str
    output_fxname: str
    quality: str
    issues: list[str]
    debug: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SuggestionResult:
    input_text: str
    candidates: list[str]
    quality: str
    issues: list[str]
    debug: dict[str, Any] = field(default_factory=dict)
