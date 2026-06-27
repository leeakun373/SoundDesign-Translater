"""Preference profiles for deterministic FXName normalization."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class FXPreferences:
    name: str = "Default"
    preserve_order: bool = True
    allow_distance_in_fxname: bool = True
    boom_can_reorder: bool = False
    boom_suggestion_only: bool = True


class PreferenceStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._profiles: dict[str, FXPreferences] = {"Default": FXPreferences()}
        if path and path.is_file():
            self.load()

    def get(self, name: str = "Default") -> FXPreferences:
        return self._profiles.get(name, self._profiles["Default"])

    def set(self, profile: FXPreferences) -> None:
        self._profiles[profile.name] = profile
        self.save()

    def names(self) -> list[str]:
        return sorted(self._profiles)

    def load(self) -> None:
        if not self.path or not self.path.is_file():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        profiles = data.get("profiles", {}) if isinstance(data, dict) else {}
        for name, values in profiles.items():
            self._profiles[name] = FXPreferences(name=name, **{k: v for k, v in values.items() if k != "name"})

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "profiles": {name: asdict(profile) for name, profile in sorted(self._profiles.items())},
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
