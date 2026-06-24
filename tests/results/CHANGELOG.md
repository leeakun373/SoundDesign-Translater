# 测试修复记录 — 2026-06-14

## 测试结果

| 指标 | 数值 |
|------|------|
| 用例总数 | 40 |
| PASS | 40 (100%) |
| 最新报告 | [latest_report.md](./latest_report.md) |

## 如何复跑

```powershell
python tests/run_all_tests.py
# 或 run_tests.bat
```

## 本次修复项

### 1. 文件名 Hi / FIRING 误译
- `Hi`/`Lo`/`FIRING`/`Pounder` 加入文件名保留词或 overrides 永不翻译

### 2. 混合中英文输入方向错误
- 修复：`detect_lang_pair` 含中文且比例足够时优先走中→英组装

### 3. 中→英组装增强
- 输入中已有英文词直接保留；扩展 `zh_oral_aliases.csv`

### 4. 测试基础设施
- `tests/run_all_tests.py` — 40 条自动化用例
- `tests/results/` — latest 报告 + 历史 run_* 已 gitignore

## 用例覆盖

- 英→中 文件名 ×10
- 英→中 句子 ×8
- 中→英 FX ×15
- 中→英 口语 ×7
