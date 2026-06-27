"""Canonical token lookup backed by maintainable CSV data and glossary fallback."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from glossary.fx_slots import infer_slot
from glossary.matcher import GlossaryMatcher
from glossary.zh_compose import FILLER_CHARS, FILLER_PHRASES, build_compose_index


DEFAULT_CANONICAL_PATH = Path(__file__).resolve().parent / "data" / "canonical_tokens.csv"
CANONICAL_SLOTS = {
    "material",
    "object",
    "source",
    "action",
    "motion",
    "detail",
    "modifier",
}


@dataclass(frozen=True)
class CanonicalToken:
    raw: str
    canonical: str
    slot: str
    lang: str
    priority: int
    tags: str = ""
    note: str = ""


@dataclass(frozen=True)
class CanonicalMatch:
    raw: str
    canonical: str | None
    slot: str
    source: str
    status: str
    issues: list[str]


class CanonicalDB:
    def __init__(
        self,
        matcher: GlossaryMatcher | None = None,
        canonical_path: Path | None = None,
    ) -> None:
        self.matcher = matcher or GlossaryMatcher()
        self.canonical_path = canonical_path or DEFAULT_CANONICAL_PATH
        self._tokens = _load_canonical_tokens(self.canonical_path)
        self._zh_tokens = sorted(
            (token for token in self._tokens if token.lang == "zh"),
            key=lambda token: (len(token.raw), token.priority),
            reverse=True,
        )
        self._ascii_tokens = {
            token.raw.casefold(): token for token in self._tokens if token.lang == "en"
        }
        self._zh_index = build_compose_index(self.matcher)

    @property
    def token_count(self) -> int:
        return len(self._tokens)

    @property
    def slot_counts(self) -> dict[str, int]:
        return dict(Counter(token.slot for token in self._tokens))

    def resolve_ascii(self, raw: str) -> CanonicalMatch:
        canonical_token = self._ascii_tokens.get(raw.casefold())
        if canonical_token:
            return _token_to_match(canonical_token)
        entry = self.matcher.lookup_en(raw)
        if entry is None:
            return CanonicalMatch(
                raw=raw,
                canonical=None,
                slot="unknown",
                source="ascii",
                status="unknown",
                issues=["unknown_ascii"],
            )
        canonical = title_fx_text(entry.en)
        return CanonicalMatch(
            raw=raw,
            canonical=canonical,
            slot=infer_slot(canonical, entry.term_type),
            source="canonical_db",
            status="ok",
            issues=[],
        )

    def segment_chinese(self, text: str) -> list[CanonicalMatch]:
        out: list[CanonicalMatch] = []
        unknown: list[str] = []
        i = 0

        def flush_unknown() -> None:
            if not unknown:
                return
            raw = "".join(unknown)
            out.append(
                CanonicalMatch(
                    raw=raw,
                    canonical=None,
                    slot="unknown",
                    source="canonical_db",
                    status="unknown",
                    issues=["unknown_zh"],
                )
            )
            unknown.clear()

        ordered_fillers = sorted(FILLER_PHRASES, key=len, reverse=True)
        while i < len(text):
            canonical_token = next(
                (token for token in self._zh_tokens if text.startswith(token.raw, i)),
                None,
            )
            glossary_match = next(
                ((zh, entry) for zh, entry in self._zh_index if text.startswith(zh, i)),
                None,
            )
            if canonical_token and (
                glossary_match is None or len(canonical_token.raw) >= len(glossary_match[0])
            ):
                flush_unknown()
                out.append(_token_to_match(canonical_token))
                i += len(canonical_token.raw)
                continue

            if glossary_match:
                flush_unknown()
                zh, entry = glossary_match
                canonical = title_fx_text(entry.en)
                out.append(
                    CanonicalMatch(
                        raw=zh,
                        canonical=canonical,
                        slot=infer_slot(canonical, entry.term_type),
                        source="canonical_db",
                        status="ok",
                        issues=[],
                    )
                )
                i += len(zh)
                continue

            filler = next((phrase for phrase in ordered_fillers if text.startswith(phrase, i)), None)
            if filler:
                flush_unknown()
                out.append(CanonicalMatch(filler, None, "ignored", "filler", "ignored", []))
                i += len(filler)
                continue
            if text[i] in FILLER_CHARS:
                flush_unknown()
                out.append(CanonicalMatch(text[i], None, "ignored", "filler", "ignored", []))
                i += 1
                continue

            unknown.append(text[i])
            i += 1

        flush_unknown()
        return out


def title_fx_text(text: str) -> str:
    upper_words = {"fx", "sfx", "ucs", "bb", "ds"}
    titled: list[str] = []
    for word in text.split():
        if word.lower() in upper_words:
            titled.append(word.upper())
        elif any(ch.isdigit() for ch in word) and word.isupper():
            titled.append(word)
        else:
            titled.append(word[:1].upper() + word[1:].lower())
    return " ".join(titled)


def _token_to_match(token: CanonicalToken) -> CanonicalMatch:
    canonical = title_fx_text(token.canonical)
    return CanonicalMatch(
        raw=token.raw,
        canonical=canonical,
        slot=token.slot,
        source="canonical_csv",
        status="ok",
        issues=[],
    )


def _load_canonical_tokens(path: Path) -> list[CanonicalToken]:
    if not path.is_file():
        return []

    best: dict[tuple[str, str], CanonicalToken] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for line_number, row in enumerate(csv.DictReader(handle), start=2):
            raw = (row.get("raw") or "").strip()
            canonical = (row.get("canonical") or "").strip()
            slot = (row.get("slot") or "").strip().lower()
            lang = (row.get("lang") or "").strip().lower()
            if not raw or not canonical:
                raise ValueError(f"canonical token row {line_number} requires raw and canonical")
            if slot not in CANONICAL_SLOTS:
                raise ValueError(f"canonical token row {line_number} has invalid slot: {slot}")
            if lang not in {"zh", "en"}:
                raise ValueError(f"canonical token row {line_number} has invalid lang: {lang}")
            try:
                priority = int((row.get("priority") or "0").strip())
            except ValueError as exc:
                raise ValueError(
                    f"canonical token row {line_number} has invalid priority"
                ) from exc
            token = CanonicalToken(
                raw=raw,
                canonical=canonical,
                slot=slot,
                lang=lang,
                priority=priority,
                tags=(row.get("tags") or "").strip(),
                note=(row.get("note") or "").strip(),
            )
            key = (lang, raw.casefold())
            if key not in best or token.priority > best[key].priority:
                best[key] = token
    return sorted(best.values(), key=lambda token: (token.lang, token.raw.casefold()))
