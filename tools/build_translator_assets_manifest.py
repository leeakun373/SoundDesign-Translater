#!/usr/bin/env python3
"""Build translator_assets/MANIFEST.json with SHA256 and sync metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "translator_assets"
MANIFEST = ASSETS / "MANIFEST.json"

# role, sync_mode: data|code|generated|large
TRACKED = (
    ("fxname/fx_overrides.csv", "fxname_manual", "data"),
    ("fxname/fx_overrides_auto.csv", "fxname_auto", "data"),
    ("fxname/fx_overrides_bilingual.csv", "fxname_bilingual", "data"),
    ("fxname/fx_overrides_phrase.csv", "fxname_phrase", "data"),
    ("fxname/zh_en_alignment.csv", "zh_en_alignment", "generated"),
    ("generated/jieba_userdict.txt", "jieba_userdict", "generated"),
    ("canonical/canonical_tokens.csv", "canonical_snapshot", "data"),
    ("glossary/user_overrides.csv", "glossary_user", "data"),
    ("glossary/zh_oral_aliases.csv", "glossary_oral", "data"),
    ("glossary/sources/MyKeyWordV1.csv", "mykeyword", "data"),
    ("glossary/sources/ucs_catid_list.csv", "ucs_catid", "data"),
    ("glossary/sources/ucs_categorylist.csv", "ucs_official", "data"),
    ("dictionaries/cedict_ts.u8", "cedict", "data"),
    ("indexes/audio_glossary.sqlite", "audio_glossary_db", "data"),
    ("indexes/boom_style_index.sqlite", "boom_style_index", "large"),
    ("supplements/pillars_data.csv", "pillars_source", "data"),
    ("supplements/lol_skinlines_zh.csv", "lol_skinlines", "data"),
    ("supplements/en_synonym_groups.csv", "en_synonyms", "data"),
    ("supplements/soundminer.tth", "soundminer_source", "data"),
    ("supplements/presets.json", "presets", "data"),
    ("supplements/ucs_catid_list.csv", "ucs_catid_supplement", "data"),
)

REBUILD = {
    "fxname/zh_en_alignment.csv": "python -m translator.align",
    "generated/jieba_userdict.txt": "python -m translator.segment --build",
    "indexes/audio_glossary.sqlite": "python glossary/build_glossary.py",
    "canonical/canonical_tokens.csv": "copy from fxengine/data/canonical_tokens.csv",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest() -> dict:
    files: list[dict] = []
    missing: list[str] = []
    for rel, role, sync_mode in TRACKED:
        path = ASSETS / rel
        item = {
            "path": rel.replace("\\", "/"),
            "role": role,
            "sync_mode": sync_mode,
            "rebuild": REBUILD.get(rel.replace("\\", "/"), ""),
        }
        if path.is_file():
            item["size"] = path.stat().st_size
            item["sha256"] = _sha256(path)
            files.append(item)
        else:
            missing.append(rel)
    return {
        "version": 1,
        "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "assets_root": "translator_assets",
        "env_override": "TRANSLATOR_ASSETS_ROOT",
        "files": files,
        "missing": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build translator_assets MANIFEST.json")
    parser.add_argument("--write", action="store_true", help="Write MANIFEST.json")
    args = parser.parse_args()
    payload = build_manifest()
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        MANIFEST.write_text(text, encoding="utf-8")
        print(f"Wrote {MANIFEST} ({len(payload['files'])} files, {len(payload['missing'])} missing)")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
