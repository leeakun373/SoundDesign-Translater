# SoundDesign Translater → UCSRenamer 同步维护

## 唯一数据源

SoundDesign Translater 是 FXName 翻译行为、代码和词表的唯一数据源。所有准确率改进必须先在本项目完成并通过测试，然后由 UCSRenamer 的同步工具生成 vendored 副本。

**禁止**直接修改 `UCSRenamer/vendor/sounddesign_translator/`。该目录是生成物，下次同步会覆盖其中的手工改动。UCSRenamer 生产运行时也不得导入、调用或依赖本项目路径。

**UCS 黄金表**（`tests/fixtures/fxname_to_fxname_zhtest.json`）只记录最终验收期望，**不得**作为修词源或反向影响 SD 输出逻辑。修词只在 SD 的 `fx_overrides*.csv`、分词与 `translator/*.py` 管线完成。

---

## 五步法：从 UCS 批测发现问题到同步验收

### 1. UCS 批测只负责发现问题（不在 vendor 里手改）

在 UCSRenamer 对 `TESTASSETS/zhtest/` 跑批测，导出问题 CSV（工具：`tools/export_zhtest_translation_issues.py`）：

| 列 | 含义 |
|---|---|
| `input` | 原始中文 FXName 输入 |
| `output` | 当前翻译输出 |
| `token_trace` | 逐 token 决策链（JSON） |
| `unknown_tokens` | 落入 unknown 的中文词元 |
| `source_layers` | 各 token 命中的源层（manual / bilingual / canonical / auto / cedict） |
| `has_cedict` | 是否用到 CC-CEDICT |
| `has_auto` | 是否用到 fx_overrides_auto |
| `has_bilingual` | 是否用到 fx_overrides_bilingual |
| `notes` | 可选备注（如 dropped_suffix、unknown_split） |

**禁止**在 UCS vendor 目录手改词表或代码来「让批测过」。

### 2. 所有修正回到 SoundDesign Translater 源项目

按问题类型改正确的源层：

| 问题类型 | 修改位置 |
|---|---|
| 孤立词误译 / 缺词 | `translator/data/fx_overrides.csv`（手工，最高优先级） |
| 相邻两词上下文歧义 | `translator/data/fx_overrides_phrase.csv` |
| 分词切碎或合并错误 | `translator/data/jieba_userdict.txt`（`segment.build_userdict()` 重建）或 `translator/segment.py` |
| 弱声学后缀误伤（如 `声→Ambience`） | `translator/fxname_mode.py` 的 `ZH_WEAK_SUFFIX` 规则 |
| unknown 整词可拆子词 | `translator/fxname_mode.py` 的 `unknown_split` 回退 |
| 槽位排序 / BOOM 吸附 | `glossary/fx_slots.py`、`translator/boom_snap.py` 等 |

轨道 B 的 `fxengine/data/canonical_tokens.csv` 仅在治理流程允许时改动；日常 FXName 修词优先走手工表。

### 3. 每个 UCS zhtest 问题都进 SD 回归

像 `狼嚎远处`、`咔哒关上门`、`户外虫鸣` 这类案例，必须进入：

- `tests/test_translator.py` 精确断言，和/或
- `tests/zh_fxname_probe_regression.csv` 探针回归（大批量场景）

**不要**只在 UCS 改黄金 JSON 而不在 SD 加测试。

### 4. SD 通过测试后再同步到 UCS

```powershell
python -m pytest tests/test_translator.py tests/test_zh_fxname_probe_regression.py -q
```

预览并同步：

```powershell
cd <UCSRenamer目录>
python tools/sync_sounddesign_translator.py --source <SoundDesign-Translater目录> --dry-run
python tools/sync_sounddesign_translator.py --source <SoundDesign-Translater目录> --apply --include-glossary-db
```

仅当 `glossary/boom_style_index.sqlite` 变化时：

```powershell
python tools/sync_translator_fxname_assets.py --source <SoundDesign-Translater目录> --apply
```

### 5. UCS 黄金只记录最终期望

仅当 SD 源端输出已证明正确后，才更新 `tests/fixtures/fxname_to_fxname_zhtest.json` 中对应 `output` 字段。

对齐与全量测试：

```powershell
python tools/compare_fxname_translation_parity.py --source <SoundDesign-Translater目录> --report QA_RESULTS/zhtest_translation_parity.md
python -m pytest tests/test_fxname_translation_runtime.py tests/test_translator_sync.py -q
python -m pytest -q
```

`QA_RESULTS/zhtest_translation_parity.md` 必须为零差异。

---

## 管线机制说明（SD 与 UCS vendor 行为一致）

### 弱声学后缀丢弃

单独成词的 `声`、`一声` 等在未进入手工表时默认 `dropped_suffix`，避免 bilingual 层 `声→Ambience` 污染 `摩擦声` 等场景。整词已在手工表策展的（如 `欢呼声`、`虫鸣`）正常 lookup，不丢弃。

### unknown 整词拆分回退

jieba 给出完整词元但四表 + cedict 均未命中时，用已知 override 键做最长匹配拆分；仅当**所有子词**均可可靠译出时才组合输出，trace 标记 `unknown_split`。

---

## 变更与同步命令对应表

| SoundDesign Translater 变更 | UCSRenamer 操作 |
|---|---|
| `translator_assets/**` 仅 CSV/SQLite（逻辑未改） | `tools/sync_translator_assets.py --source <目录> --apply --data-only` |
| `translator/`、`fxengine/`、glossary 代码 | 常规 `sync_sounddesign_translator.py` |
| `translator_assets/indexes/audio_glossary.sqlite` | 常规同步加 `--include-glossary-db` |
| `translator_assets/indexes/boom_style_index.sqlite` | `sync_translator_fxname_assets.py --apply` |
| `nllb_int8_model/` | `tools/sync_translator_model_asset.py --source <目录> --apply` |
| 仅文档或源项目测试 | 不需要运行时资产同步 |

数据根目录见 [`translator_assets/README.md`](../translator_assets/README.md)；运行时通过 `translator/paths.py` 解析，可用 `TRANSLATOR_ASSETS_ROOT` 覆盖。

## 审计与回滚

- `_SYNC_MANIFEST.json` 记录源提交、脏工作树、同步时间与 SHA256。
- 回滚时先在 SD 回退源改动，再重新同步；**禁止**只回退 UCS vendored 文件。
- 同步后重启 UCSRenamer 以重载词表缓存。

## 已修复的 zhtest 案例（示例）

| 输入 | 问题 | 修复 |
|---|---|---|
| `狼嚎远处` | `狼嚎` unknown | 手工 `狼嚎→Wolf Howl` |
| `咔哒关上门` | `关上门` unknown | 手工 `关上门→Close Door` |
| `户外虫鸣` | `虫鸣` unknown | 手工 `虫鸣→Insect Chirp` |
| `冰斧刮擦冰砖的摩擦声` | `冰斧` unknown；`声→Ambience` | 手工补词 + 弱后缀丢弃 |
| `引擎怠速轰油门` | 误分为 `轰油`+`门` | 手工 `轰油门→Revving` + userdict |
| `落叶林清晨鸟叫` | `落叶林`、`鸟叫` unknown | 手工补词 |
| `玻璃破碎` | `玻璃→Windshield`（重复键覆盖） | `挡风玻璃→Windshield`，保留 `玻璃→Glass` |
