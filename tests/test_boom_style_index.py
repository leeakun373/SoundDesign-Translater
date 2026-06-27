#!/usr/bin/env python3
"""Principle tests for Boom-style FX-name ranking."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import EN_LANG, ZH_LANG, NllbTranslator
from glossary.boom_style import BoomStyleIndex
from glossary.matcher import GlossaryMatcher


class FakeTranslator(NllbTranslator):
    def __init__(self, matcher: GlossaryMatcher, index_path: Path) -> None:
        super().__init__()
        self._translator = object()
        self._tokenizer = object()
        self._glossary = matcher
        self._boom_style = BoomStyleIndex(index_path)
        self.calls: list[str] = []

    def _nllb_translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        assert src_lang == ZH_LANG
        assert tgt_lang == EN_LANG
        self.calls.append(text)
        return {"神秘呼喊": "Howl Wolf"}.get(text, text)


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        index_path = Path(tmp) / "boom.sqlite"
        _write_test_index(index_path)
        style = BoomStyleIndex(index_path)

        styled = style.style_fx_name("Howl Wolf Rocket")
        if styled.text != "Wolf Howl Rocket":
            failures.append(f"expected Wolf Howl Rocket, got {styled.text!r}")
        if "Wolf Howl" not in styled.boom_phrase_hits:
            failures.append(f"expected Wolf Howl phrase hit, got {styled.boom_phrase_hits}")
        if styled.phrase_hits != styled.boom_phrase_hits:
            failures.append("phrase_hits alias did not return boom_phrase_hits")

        missing = BoomStyleIndex(Path(tmp) / "missing.sqlite").style_fx_name(
            "Howl Wolf Rocket"
        )
        if missing.boom_index_used or missing.text != "Howl Wolf Rocket":
            failures.append(f"missing index should be a no-op, got {missing}")

        translator = FakeTranslator(GlossaryMatcher(), index_path)
        direct = translator.translate_fxname("木门滑开")
        if direct.text != "Wood Door Slide Open":
            failures.append(f"full glossary compose should preserve order: {direct.text!r}")

        hybrid = translator.translate_fxname("木门 神秘呼喊")
        if "神秘呼喊" not in translator.calls:
            failures.append("unknown zh did not call NLLB fallback")
        for token in ("Wood", "Door", "Wolf", "Howl"):
            if token.lower() not in hybrid.text.lower():
                failures.append(f"hybrid output missed {token}: {hybrid.text!r}")
        if not hybrid.debug.get("boom_index_used"):
            failures.append(f"boom index was not marked as used: {hybrid.debug}")
        if "Front" in hybrid.text:
            failures.append(f"boom index overrode glossary term with Front: {hybrid.text!r}")

    if failures:
        print("Boom style index failures:")
        for failure in failures:
            print("-", failure)
        return 1
    print("Boom style index PASS")
    return 0


def test_phrase_hits_alias() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        index_path = Path(tmp) / "boom.sqlite"
        _write_test_index(index_path)
        result = BoomStyleIndex(index_path).style_fx_name("Howl Wolf Rocket")

        assert result.boom_index_used is True
        assert result.boom_phrase_hits
        assert result.phrase_hits == result.boom_phrase_hits


def _write_test_index(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE tokens (
                token TEXT PRIMARY KEY,
                freq INTEGER NOT NULL,
                filename_freq INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE phrases (
                phrase TEXT PRIMARY KEY,
                n INTEGER NOT NULL,
                freq INTEGER NOT NULL,
                filename_freq INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE stats (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        conn.executemany(
            "INSERT INTO tokens(token, freq, filename_freq) VALUES (?, ?, ?)",
            [
                ("wolf", 20, 10),
                ("howl", 20, 10),
                ("rocket", 12, 8),
                ("front", 99, 99),
                ("door", 10, 8),
                ("wood", 10, 8),
            ],
        )
        conn.executemany(
            "INSERT INTO phrases(phrase, n, freq, filename_freq) VALUES (?, ?, ?, ?)",
            [
                ("wolf howl", 2, 100, 80),
                ("front door", 2, 200, 100),
                ("slide door wood", 3, 500, 500),
                ("wood door", 2, 20, 20),
            ],
        )


if __name__ == "__main__":
    raise SystemExit(main())
