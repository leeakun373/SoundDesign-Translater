"""Canonical token lookup over the existing glossary with small v0.3 gaps filled."""

from __future__ import annotations

from dataclasses import dataclass

from glossary.fx_slots import infer_slot
from glossary.matcher import GlossaryMatcher
from glossary.zh_compose import FILLER_CHARS, FILLER_PHRASES, build_compose_index


CANONICAL_ZH_OVERRIDES: dict[str, tuple[str, str]] = {
    "发射": ("Launch", "action"),
}


@dataclass(frozen=True)
class CanonicalMatch:
    raw: str
    canonical: str | None
    slot: str
    source: str
    status: str
    issues: list[str]


class CanonicalDB:
    def __init__(self, matcher: GlossaryMatcher | None = None) -> None:
        self.matcher = matcher or GlossaryMatcher()
        self._zh_index = build_compose_index(self.matcher)

    def resolve_ascii(self, raw: str) -> CanonicalMatch:
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

        ordered_overrides = sorted(CANONICAL_ZH_OVERRIDES.items(), key=lambda item: len(item[0]), reverse=True)
        ordered_fillers = sorted(FILLER_PHRASES, key=len, reverse=True)
        while i < len(text):
            override = next(
                ((zh, value) for zh, value in ordered_overrides if text.startswith(zh, i)),
                None,
            )
            if override:
                flush_unknown()
                zh, (canonical, slot) = override
                out.append(CanonicalMatch(zh, canonical, slot, "canonical_override", "ok", []))
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

            matched = next(((zh, entry) for zh, entry in self._zh_index if text.startswith(zh, i)), None)
            if matched:
                flush_unknown()
                zh, entry = matched
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
