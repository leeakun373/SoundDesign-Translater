"""Canonical token lookup backed by governed CSV data and glossary fallback."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from glossary.fx_slots import infer_slot
from glossary.matcher import GlossaryEntry, GlossaryMatcher
from glossary.zh_compose import FILLER_CHARS, FILLER_PHRASES, build_compose_index


DEFAULT_CANONICAL_PATH = Path(__file__).resolve().parent / "data" / "canonical_tokens.csv"
CANONICAL_COLUMNS = (
    "raw",
    "canonical",
    "slot",
    "lang",
    "priority",
    "rule_type",
    "review_status",
    "ambiguity",
    "tags",
    "source",
    "note",
)
LEGACY_CANONICAL_COLUMNS = (
    "raw",
    "canonical",
    "slot",
    "lang",
    "priority",
    "tags",
    "note",
)
ALLOWED_SLOTS = {
    "action",
    "material",
    "object",
    "source",
    "motion",
    "detail",
    "modifier",
    "unknown",
}
ALLOWED_LANGS = {"zh", "en", "mixed", "pinyin"}
ALLOWED_RULE_TYPES = {
    "phrase",
    "stable_single",
    "stable_single_low_confidence",
    "phrase_low_confidence",
    "ambiguous_single",
    "ambiguous_phrase",
    "weak_token",
    "suffix_only",
}
ALLOWED_REVIEW_STATUSES = {"keep", "review", "reject"}
ALLOWED_AMBIGUITY = {"low", "medium", "high"}
ALLOWED_SOURCES = {
    "manual",
    "ai_candidate",
    "ai_reviewed",
    "boom_mined",
    "glossary_seed",
}

# Backwards-compatible public name used by existing callers and tests.
CANONICAL_SLOTS = ALLOWED_SLOTS

USER_TOKEN_PREFIXES = (
    "请帮我做",
    "请帮我",
    "帮我做",
    "我想要",
    "听起来像",
    "听起来",
    "这是一个",
    "这是",
    "非常",
    "比较",
    "有点",
    "很",
)
USER_TOKEN_FILLERS = frozenset(
    {
        "的",
        "然后",
        "一下",
        "一个",
        "请帮我做",
        "请帮我",
        "帮我做",
        "我想要",
        "听起来像",
        "听起来",
        "这是一个",
        "这是",
        "请帮我翻译",
        "这个声音是",
        "非常",
        "比较",
        "有点",
        "很",
    }
)


@dataclass(frozen=True)
class CanonicalToken:
    raw: str
    canonical: str
    slot: str
    lang: str
    priority: int
    rule_type: str
    review_status: str
    ambiguity: str
    tags: str = ""
    source: str = "manual"
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
        self._all_tokens = load_canonical_rows(self.canonical_path)
        self._tokens = _select_runtime_tokens(self._all_tokens)
        self._zh_tokens = sorted(
            (token for token in self._tokens if _uses_zh_index(token)),
            key=lambda token: (len(token.raw), token.priority),
            reverse=True,
        )
        self._zh_exact = {token.raw: token for token in self._zh_tokens}
        self._ascii_tokens = {
            token.raw.casefold(): token
            for token in self._tokens
            if _uses_ascii_index(token)
        }
        non_runtime = [
            token for token in self._all_tokens if token.review_status != "keep"
        ]
        # These are suppression guards, not positive lookup indexes. They prevent a
        # reviewed alias (for example 划过) from leaking back through the glossary.
        self._non_runtime_zh = sorted(
            {token.raw for token in non_runtime if _uses_zh_index(token)},
            key=len,
            reverse=True,
        )
        self._non_runtime_zh_exact = set(self._non_runtime_zh)
        self._non_runtime_ascii = {
            token.raw.casefold()
            for token in non_runtime
            if _uses_ascii_index(token)
        }
        self._zh_index = build_compose_index(self.matcher)
        self._zh_glossary_exact: dict[str, GlossaryEntry] = {}
        for raw, entry in self._zh_index:
            self._zh_glossary_exact.setdefault(raw, entry)

    @property
    def token_count(self) -> int:
        """Number of rows available to runtime normalization (keep only)."""
        return len(self._tokens)

    @property
    def runtime_token_count(self) -> int:
        return self.token_count

    @property
    def raw_csv_row_count(self) -> int:
        return len(self._all_tokens)

    @property
    def review_row_count(self) -> int:
        return sum(token.review_status == "review" for token in self._all_tokens)

    @property
    def reject_row_count(self) -> int:
        return sum(token.review_status == "reject" for token in self._all_tokens)

    @property
    def slot_counts(self) -> dict[str, int]:
        return dict(Counter(token.slot for token in self._tokens))

    def resolve_ascii(self, raw: str) -> CanonicalMatch:
        canonical_token = self._ascii_tokens.get(raw.casefold())
        if canonical_token:
            return _token_to_match(canonical_token)
        if raw.casefold() in self._non_runtime_ascii:
            return CanonicalMatch(
                raw=raw,
                canonical=None,
                slot="unknown",
                source="canonical_review",
                status="unknown",
                issues=["unknown_ascii", "canonical_review_required"],
            )
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

    def resolve_chinese_user_token(self, raw: str) -> CanonicalMatch:
        """Resolve one explicit Chinese user token without segmenting its core."""
        cleaned = cleanup_chinese_user_token(raw)
        if not cleaned:
            return CanonicalMatch(
                raw=raw,
                canonical=None,
                slot="ignored",
                source="filler",
                status="ignored",
                issues=[],
            )

        canonical_token = self._zh_exact.get(cleaned)
        if canonical_token:
            return _token_to_match(canonical_token)
        if cleaned in self._non_runtime_zh_exact:
            return CanonicalMatch(
                raw=cleaned,
                canonical=None,
                slot="unknown",
                source="canonical_review",
                status="unknown",
                issues=["unknown_zh", "canonical_review_required"],
            )

        glossary_entry = self._zh_glossary_exact.get(cleaned)
        if glossary_entry is not None and len(cleaned) > 1:
            canonical = title_fx_text(glossary_entry.en)
            return CanonicalMatch(
                raw=cleaned,
                canonical=canonical,
                slot=infer_slot(canonical, glossary_entry.term_type),
                source="glossary_fallback",
                status="ok",
                issues=[],
            )

        return CanonicalMatch(
            raw=cleaned,
            canonical=None,
            slot="unknown",
            source="user_token",
            status="unknown",
            issues=["unknown_zh"],
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
            blocked_raw = next(
                (raw for raw in self._non_runtime_zh if text.startswith(raw, i)),
                None,
            )
            glossary_match = next(
                ((zh, entry) for zh, entry in self._zh_index if text.startswith(zh, i)),
                None,
            )
            if glossary_match and len(glossary_match[0]) == 1:
                glossary_match = None
            canonical_length = len(canonical_token.raw) if canonical_token else 0
            blocked_length = len(blocked_raw) if blocked_raw else 0
            glossary_length = len(glossary_match[0]) if glossary_match else 0

            if canonical_token and canonical_length >= max(
                blocked_length, glossary_length
            ):
                flush_unknown()
                out.append(_token_to_match(canonical_token))
                i += canonical_length
                continue

            if blocked_raw and blocked_length >= glossary_length:
                flush_unknown()
                out.append(
                    CanonicalMatch(
                        raw=blocked_raw,
                        canonical=None,
                        slot="unknown",
                        source="canonical_review",
                        status="unknown",
                        issues=["unknown_zh", "canonical_review_required"],
                    )
                )
                i += blocked_length
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

            filler = next(
                (phrase for phrase in ordered_fillers if text.startswith(phrase, i)),
                None,
            )
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


def cleanup_chinese_user_token(raw: str) -> str:
    """Apply boundary-only cleanup without splitting or changing token core."""
    cleaned = raw.strip()
    if not cleaned or cleaned in USER_TOKEN_FILLERS:
        return ""
    for prefix in USER_TOKEN_PREFIXES:
        if cleaned.startswith(prefix) and len(cleaned) > len(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    if cleaned.endswith("的") and len(cleaned) > 1:
        cleaned = cleaned[:-1]
    return "" if cleaned in USER_TOKEN_FILLERS else cleaned


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


def infer_rule_type(raw: str, lang: str) -> str:
    if lang == "zh" and len(raw) == 1:
        return "stable_single"
    return "phrase"


def parse_canonical_row(
    row: Mapping[str, str | None], line_number: int = 0
) -> CanonicalToken:
    """Parse one row, applying defaults only for columns absent from old CSVs."""
    location = f"canonical token row {line_number}" if line_number else "canonical token row"
    raw = _row_value(row, "raw")
    canonical = _row_value(row, "canonical")
    slot = _row_value(row, "slot").lower()
    lang = _row_value(row, "lang").lower()
    review_status = _row_value(row, "review_status", "keep").lower()
    rule_type = _row_value(row, "rule_type", infer_rule_type(raw, lang)).lower()
    ambiguity = _row_value(row, "ambiguity", "low").lower()
    source = _row_value(row, "source", "manual").lower()

    if not raw:
        raise ValueError(f"{location} requires raw")
    if review_status not in ALLOWED_REVIEW_STATUSES:
        raise ValueError(f"{location} has invalid review_status: {review_status}")
    if review_status == "keep" and not canonical:
        raise ValueError(f"{location} with review_status=keep requires canonical")
    if slot not in ALLOWED_SLOTS:
        raise ValueError(f"{location} has invalid slot: {slot}")
    if lang not in ALLOWED_LANGS:
        raise ValueError(f"{location} has invalid lang: {lang}")
    if rule_type not in ALLOWED_RULE_TYPES:
        raise ValueError(f"{location} has invalid rule_type: {rule_type}")
    if ambiguity not in ALLOWED_AMBIGUITY:
        raise ValueError(f"{location} has invalid ambiguity: {ambiguity}")
    if source not in ALLOWED_SOURCES:
        raise ValueError(f"{location} has invalid source: {source}")
    try:
        priority = int(_row_value(row, "priority"))
    except ValueError as exc:
        raise ValueError(f"{location} has invalid priority") from exc
    if not 0 <= priority <= 100:
        raise ValueError(f"{location} has invalid priority: {priority}")

    return CanonicalToken(
        raw=raw,
        canonical=canonical,
        slot=slot,
        lang=lang,
        priority=priority,
        rule_type=rule_type,
        review_status=review_status,
        ambiguity=ambiguity,
        tags=_row_value(row, "tags"),
        source=source,
        note=_row_value(row, "note"),
    )


def load_canonical_rows(path: Path) -> list[CanonicalToken]:
    if not path.is_file():
        return []
    rows: list[CanonicalToken] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for line_number, row in enumerate(reader, start=2):
            rows.append(parse_canonical_row(row, line_number))
    return rows


def canonical_token_to_row(token: CanonicalToken) -> dict[str, str | int]:
    return {column: getattr(token, column) for column in CANONICAL_COLUMNS}


def _load_canonical_tokens(path: Path) -> list[CanonicalToken]:
    """Backwards-compatible loader name; returns runtime keep rows only."""
    return _select_runtime_tokens(load_canonical_rows(path))


def _select_runtime_tokens(rows: list[CanonicalToken]) -> list[CanonicalToken]:
    best: dict[tuple[str, str], CanonicalToken] = {}
    for token in rows:
        if token.review_status != "keep":
            continue
        key = (token.lang, token.raw.casefold())
        if key not in best or token.priority > best[key].priority:
            best[key] = token
    return sorted(best.values(), key=lambda token: (token.lang, token.raw.casefold()))


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


def _row_value(
    row: Mapping[str, str | None], name: str, default_if_missing: str = ""
) -> str:
    if name not in row:
        return default_if_missing
    return (row.get(name) or "").strip()


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _uses_zh_index(token: CanonicalToken) -> bool:
    return token.lang == "zh" or (token.lang == "mixed" and _contains_cjk(token.raw))


def _uses_ascii_index(token: CanonicalToken) -> bool:
    return token.lang in {"en", "pinyin"} or (
        token.lang == "mixed" and not _contains_cjk(token.raw)
    )
