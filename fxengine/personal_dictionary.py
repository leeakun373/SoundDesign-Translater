"""Small persistent personal alias dictionary."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class PersonalEntry:
    alias: str
    canonical: str | None
    action: str = "map"


class PersonalDictionary:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._entries: dict[str, PersonalEntry] = {}
        if path and path.is_file():
            self.load()

    def add_alias(self, alias: str, canonical: str) -> PersonalEntry:
        entry = PersonalEntry(alias.strip(), canonical.strip(), "map")
        self._entries[_key(alias)] = entry
        self.save()
        return entry

    def keep_raw(self, alias: str) -> PersonalEntry:
        entry = PersonalEntry(alias.strip(), alias.strip(), "keep")
        self._entries[_key(alias)] = entry
        self.save()
        return entry

    def ignore(self, alias: str) -> PersonalEntry:
        entry = PersonalEntry(alias.strip(), None, "ignore")
        self._entries[_key(alias)] = entry
        self.save()
        return entry

    def remove_alias(self, alias: str) -> bool:
        removed = self._entries.pop(_key(alias), None)
        if removed is None:
            return False
        self.save()
        return True

    def entries(self) -> list[PersonalEntry]:
        return sorted(self._entries.values(), key=lambda entry: entry.alias.casefold())

    def resolve_entry(self, alias: str) -> PersonalEntry | None:
        return self._entries.get(_key(alias))

    def resolve(self, alias: str) -> str | None:
        entry = self.resolve_entry(alias)
        return entry.canonical if entry and entry.action != "ignore" else None

    def load(self) -> None:
        self._entries = {}
        if not self.path or not self.path.is_file():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        entries = data.get("entries", {}) if isinstance(data, dict) else {}
        for key, value in entries.items():
            if isinstance(value, str):
                entry = PersonalEntry(key, value, "map")
            else:
                entry = PersonalEntry(
                    alias=str(value.get("alias", key)),
                    canonical=value.get("canonical"),
                    action=str(value.get("action", "map")),
                )
            self._entries[_key(entry.alias)] = entry

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "entries": {key: asdict(value) for key, value in sorted(self._entries.items())},
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _key(value: str) -> str:
    return value.strip().casefold()
