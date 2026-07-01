# translator_assets

翻译运行时数据根目录（不含 NLLB 模型）。逻辑代码仍在 `translator/`、`glossary/*.py`。

## 子目录

| 目录 | 内容 |
|------|------|
| `fxname/` | 四张 override 表、`zh_en_alignment.csv` |
| `canonical/` | `canonical_tokens.csv` 只读快照（治理仍改 `fxengine/data/`） |
| `glossary/` | `user_overrides.csv`、`zh_oral_aliases.csv`、`sources/` |
| `dictionaries/` | `cedict_ts.u8` |
| `indexes/` | `audio_glossary.sqlite`、`boom_style_index.sqlite` |
| `generated/` | `jieba_userdict.txt`（可重建） |
| `supplements/` | pillars、soundminer、UCS 补充原料与 ingest 产物 |

## 环境变量

`TRANSLATOR_ASSETS_ROOT` 可指向 vendored 副本（UCS 同步后默认为 `vendor/sounddesign_translator/translator_assets`）。

## 维护命令

```powershell
python tools/build_translator_assets_manifest.py --write
python tools/audit_ucs_coverage.py
python tools/ingest_soundminer_synonyms.py
python tools/ingest_ucs_zh_synonyms.py          # 预览
python tools/ingest_ucs_zh_synonyms.py --apply  # 写入后自动 align
python tools/ingest_pillars_lol.py --apply
python glossary/build_glossary.py
python -m translator.segment --build
```

## UCS 仅数据同步

```powershell
python tools/sync_translator_assets.py --source <SD目录> --apply --data-only
```
