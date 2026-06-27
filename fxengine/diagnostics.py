"""Serialization helpers for UI and compatibility debug output."""

from __future__ import annotations

from dataclasses import asdict

from fxengine.models import FXNameResult, FXToken


def token_to_dict(token: FXToken) -> dict:
    return asdict(token)


def result_to_debug(result: FXNameResult) -> dict:
    return {
        **result.debug,
        "mode": result.mode,
        "quality": result.quality,
        "issues": list(result.issues),
        "unknowns": list(result.unknowns),
        "tokens": [token_to_dict(token) for token in result.tokens],
        "boom_confidence": result.boom_confidence,
        "boom_suggestion": result.boom_suggestion,
    }
