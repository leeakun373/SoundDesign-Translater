"""Boom/Soundminer-style English FX-name ranking from a local metadata index."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BOOM_INDEX = Path(__file__).resolve().parent / "boom_style_index.sqlite"
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-]*")


@dataclass(frozen=True)
class BoomStyleResult:
    text: str
    boom_index_used: bool
    boom_phrase_hits: list[str] = field(default_factory=list)
    selected_terms: list[str] = field(default_factory=list)


class BoomStyleIndex:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DEFAULT_BOOM_INDEX
        self.available = self.db_path.is_file()

    def style_fx_name(self, text: str, preserve_order: bool = False) -> BoomStyleResult:
        terms = _extract_terms(text)
        if not terms:
            return BoomStyleResult("", self.available)
        if not self.available:
            return BoomStyleResult(" ".join(terms), False, [], terms)

        phrase_hits = self._phrase_hits(terms)
        if preserve_order:
            return BoomStyleResult(" ".join(terms), True, phrase_hits, terms)
        best_terms = self._best_order(terms)
        best_hits = self._phrase_hits(best_terms)
        hits = best_hits or phrase_hits
        return BoomStyleResult(" ".join(best_terms), True, hits, best_terms)

    def _best_order(self, terms: list[str]) -> list[str]:
        if len(terms) > 10:
            return terms
        candidates = [terms]
        for phrase in self._candidate_phrases(terms):
            words = phrase.split()
            remaining = _remove_phrase_words(terms, words)
            if len(remaining) != len(terms) - len(words):
                continue
            candidates.append(words + remaining)
            candidates.append(remaining + words)
        return max(candidates, key=self._score_terms)

    def _score_terms(self, terms: list[str]) -> tuple[float, int]:
        score = 0.0
        hits = 0
        with sqlite3.connect(self.db_path) as conn:
            for term in terms:
                row = conn.execute(
                    "SELECT freq, filename_freq FROM tokens WHERE token = ?",
                    (term.lower(),),
                ).fetchone()
                if row:
                    score += float(row[0]) + float(row[1]) * 0.5
            for n in range(4, 1, -1):
                for i in range(0, len(terms) - n + 1):
                    phrase = " ".join(t.lower() for t in terms[i : i + n])
                    row = conn.execute(
                        "SELECT freq, filename_freq FROM phrases WHERE phrase = ?",
                        (phrase,),
                    ).fetchone()
                    if row:
                        hits += 1
                        score += (float(row[0]) + float(row[1]) * 0.75) * n * 8.0
        return score, hits

    def _candidate_phrases(self, terms: list[str]) -> list[str]:
        normalized = {t.lower() for t in terms}
        out: list[tuple[int, int, str]] = []
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT phrase, n, freq + filename_freq AS weight
                FROM phrases
                WHERE n BETWEEN 2 AND 4
                ORDER BY weight DESC, n DESC
                LIMIT 300
                """
            )
            for phrase, n, weight in rows:
                words = phrase.split()
                if all(w in normalized for w in words):
                    out.append((int(weight or 0), int(n or 0), _title_phrase(phrase)))
        out.sort(reverse=True)
        return [phrase for _weight, _n, phrase in out[:24]]

    def _phrase_hits(self, terms: list[str]) -> list[str]:
        hits: list[str] = []
        with sqlite3.connect(self.db_path) as conn:
            for n in range(4, 1, -1):
                for i in range(0, len(terms) - n + 1):
                    phrase = " ".join(t.lower() for t in terms[i : i + n])
                    row = conn.execute(
                        "SELECT 1 FROM phrases WHERE phrase = ?",
                        (phrase,),
                    ).fetchone()
                    if row:
                        title = _title_phrase(phrase)
                        if title not in hits:
                            hits.append(title)
        return hits


def _extract_terms(text: str) -> list[str]:
    articles = {"the", "a", "an"}
    terms: list[str] = []
    for word in WORD_RE.findall(text):
        if word.lower() in articles:
            continue
        terms.append(_title_word(word))
    return terms


def _remove_phrase_words(terms: list[str], words: list[str]) -> list[str]:
    needed = [w.lower() for w in words]
    out: list[str] = []
    for term in terms:
        lower = term.lower()
        if lower in needed:
            needed.remove(lower)
        else:
            out.append(term)
    return out if not needed else terms


def _title_phrase(phrase: str) -> str:
    return " ".join(_title_word(w) for w in phrase.split())


def _title_word(word: str) -> str:
    upper_words = {"fx", "sfx", "ucs", "bb", "ds"}
    if word.lower() in upper_words:
        return word.upper()
    return word[:1].upper() + word[1:].lower()
