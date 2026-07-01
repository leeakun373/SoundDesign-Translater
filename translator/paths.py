"""Central paths for translation data assets (translator_assets/).

Override root with env TRANSLATOR_ASSETS_ROOT for tests or vendored layouts.
Legacy paths under translator/data and glossary/ remain as fallbacks when the
primary asset file is missing (one-release compatibility shim).
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_ROOT = Path(os.environ.get("TRANSLATOR_ASSETS_ROOT", PROJECT_ROOT / "translator_assets"))


def _resolve(primary: Path, *legacy: Path) -> Path:
    if primary.is_file():
        return primary
    for path in legacy:
        if path.is_file():
            return path
    return primary


# --- fxname tables ---
FX_OVERRIDES_PATH = _resolve(
    ASSETS_ROOT / "fxname" / "fx_overrides.csv",
    PROJECT_ROOT / "translator" / "data" / "fx_overrides.csv",
)
FX_OVERRIDES_AUTO_PATH = _resolve(
    ASSETS_ROOT / "fxname" / "fx_overrides_auto.csv",
    PROJECT_ROOT / "translator" / "data" / "fx_overrides_auto.csv",
)
FX_OVERRIDES_BILINGUAL_PATH = _resolve(
    ASSETS_ROOT / "fxname" / "fx_overrides_bilingual.csv",
    PROJECT_ROOT / "translator" / "data" / "fx_overrides_bilingual.csv",
)
FX_OVERRIDES_PHRASE_PATH = _resolve(
    ASSETS_ROOT / "fxname" / "fx_overrides_phrase.csv",
    PROJECT_ROOT / "translator" / "data" / "fx_overrides_phrase.csv",
)
ALIGN_PATH = _resolve(
    ASSETS_ROOT / "fxname" / "zh_en_alignment.csv",
    PROJECT_ROOT / "translator" / "data" / "zh_en_alignment.csv",
)
USERDICT_PATH = _resolve(
    ASSETS_ROOT / "generated" / "jieba_userdict.txt",
    PROJECT_ROOT / "translator" / "data" / "jieba_userdict.txt",
)

# --- canonical (runtime reads fxengine; snapshot for sync/packaging) ---
CANONICAL_PATH = PROJECT_ROOT / "fxengine" / "data" / "canonical_tokens.csv"
CANONICAL_SNAPSHOT_PATH = _resolve(
    ASSETS_ROOT / "canonical" / "canonical_tokens.csv",
    CANONICAL_PATH,
)

# --- glossary sentence-mode tables ---
USER_OVERRIDES_PATH = _resolve(
    ASSETS_ROOT / "glossary" / "user_overrides.csv",
    PROJECT_ROOT / "glossary" / "user_overrides.csv",
)
ZH_ORAL_ALIASES_PATH = _resolve(
    ASSETS_ROOT / "glossary" / "zh_oral_aliases.csv",
    PROJECT_ROOT / "glossary" / "zh_oral_aliases.csv",
)
MY_KEYWORD_CSV = _resolve(
    ASSETS_ROOT / "glossary" / "sources" / "MyKeyWordV1.csv",
    PROJECT_ROOT / "glossary" / "sources" / "MyKeyWordV1.csv",
)
UCS_CATID_CSV = _resolve(
    ASSETS_ROOT / "glossary" / "sources" / "ucs_catid_list.csv",
    PROJECT_ROOT / "glossary" / "sources" / "ucs_catid_list.csv",
)
UCS_OFFICIAL_CSV = _resolve(
    ASSETS_ROOT / "glossary" / "sources" / "ucs_categorylist.csv",
    PROJECT_ROOT / "glossary" / "sources" / "ucs_categorylist.csv",
)
EN_SYNONYM_GROUPS_CSV = ASSETS_ROOT / "supplements" / "en_synonym_groups.csv"

# --- dictionaries & indexes ---
CEDICT_PATH = _resolve(
    ASSETS_ROOT / "dictionaries" / "cedict_ts.u8",
    PROJECT_ROOT / "glossary" / "sources" / "cc-cedict" / "cedict_ts.u8",
)
BOOM_INDEX_PATH = _resolve(
    ASSETS_ROOT / "indexes" / "boom_style_index.sqlite",
    PROJECT_ROOT / "glossary" / "boom_style_index.sqlite",
)
AUDIO_GLOSSARY_DB = _resolve(
    ASSETS_ROOT / "indexes" / "audio_glossary.sqlite",
    PROJECT_ROOT / "glossary" / "audio_glossary.sqlite",
)

# --- supplements (ingest inputs/outputs) ---
SUPPLEMENTS_DIR = ASSETS_ROOT / "supplements"
PILLARS_DATA_CSV = SUPPLEMENTS_DIR / "pillars_data.csv"
LOL_SKINLINES_ZH_CSV = SUPPLEMENTS_DIR / "lol_skinlines_zh.csv"
PRESETS_JSON = SUPPLEMENTS_DIR / "presets.json"
SOUNDMINER_TTH = SUPPLEMENTS_DIR / "soundminer.tth"
MANIFEST_PATH = ASSETS_ROOT / "MANIFEST.json"

# align build input (not relocated)
CANDIDATES_PATH = PROJECT_ROOT / "docs" / "boom_mining" / "boom_one_mining_v0_1_b001_candidates.csv"
