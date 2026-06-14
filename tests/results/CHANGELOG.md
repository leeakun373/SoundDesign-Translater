# 测试修复记录 — 2026-06-14

## 测试结果

| 指标 | 数值 |
|------|------|
| 用例总数 | 40 |
| PASS | 40 (100%) |
| 最新报告 | [latest_report.md](./latest_report.md) |

## 如何复跑

```powershell
cd e:\WorkSpace\LocalTranslateShared
python tests/run_all_tests.py
# 或双击 run_tests.bat
```

## 本次修复项

### 1. 文件名 Hi / FIRING 误译
- `Hi`/`Lo`/`FIRING`/`Pounder` 加入文件名保留词或 overrides 永不翻译
- 修复：`GUNCano_FIRING... Hi.wav` 不再出现「您好」「机枪」

### 2. 混合中英文输入方向错误
- 如「关门声关闭 exterior shut」「木地板脚步 parquet」被误判为英→中
- 修复：`detect_lang_pair` 含中文且比例足够时优先走中→英组装

### 3. 中→英组装增强
- 输入中已有英文词（parquet、shut）直接保留
- 扩展 `zh_oral_aliases.csv`：底噪、嗖、飞过去、木地板、脚步、弓箭等

### 4. 测试基础设施
- `tests/run_all_tests.py` — 40 条自动化用例
- `tests/results/` — 每次运行快照 + latest 报告

## 用例覆盖

- 英→中 文件名 ×10
- 英→中 句子 ×8
- 中→英 FX ×15
- 中→英 口语 ×7
