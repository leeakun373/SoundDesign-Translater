# FXName 中文测试用例规范

## 两种测试

| 类型 | 测什么 | 关键列 |
|------|--------|--------|
| **治理测试** | 这个词该不该进主表、该不该 review | `expected_review_status`, `expected_source`, `confidence_band` |
| **结果测试** | 最终 FXName 是什么、不能出现什么 | `expected_fxname`, `must_not_contain` |

一批用例可以同时是 `both`：稳定短语通常治理与结果都要验。

## CSV 列说明

| 列 | 用途 |
|----|------|
| `test_kind` | `governance` / `result` / `both` |
| `expected_canonical` | 词或短语应映射的 canonical；多选可用 `\|` |
| `expected_fxname` | 最终期望 FXName；治理-only 行留空 |
| `expected_review_status` | `mapped_canonical` / `mapped_phrase` / `review_required` / `weak_token` / `ignored` |
| `expected_source` | `stable_single` / `phrase_rule` / `ambiguity_rule` / `weak_token_rule` / `composite_phrase` |
| `confidence_band` | `high` / `medium` / `low` |
| `must_not_contain` | 禁止出现的错误 token，`\|` 分隔 |

`governance_class` 列（如 `result` / `composite`）**仅供文档分组**，runner 不读取；断言只看 `test_kind`。

## 批次

| 文件 | 内容 |
|------|------|
| `zh_fxname_governance_cases_50.csv` | 批次 1：治理四类基线（50 条） |
| `zh_fxname_governance_cases_150.csv` | 批次 1 + 扩充 051–150（100 条） |
| `zh_fxname_cases_expansion_notes.md` | 扩充说明与失败模式 |
| `zh_fxname_cases_batch2_plan.md` | 脏输入 / 元数据剥离计划（待编写） |

## 运行

```bash
python tools/run_zh_fxname_cases.py --csv tests/zh_fxname_governance_cases_50.csv
python tools/run_zh_fxname_cases.py --csv tests/zh_fxname_governance_cases_150.csv \
  --report tests/results/zh_fxname_governance_report_150.json
python -m pytest tests/test_zh_fxname_governance_cases.py -q
```

报告：

- `tests/results/zh_fxname_governance_report.json`（50 条）
- `tests/results/zh_fxname_governance_report_150.json`（150 条）

Runner 退出码：有 fail 时为 1。**不要求全 pass**；fail 是 regression baseline。

## Runner 限制（不改 engine 硬适配）

- `expected_source` 与引擎 token `source`（`canonical_csv` 等） taxonomy 不同 → 记 **pending**，非 hard fail
- `weak_token` vs `review_required` 单字边界 → 部分记 pending
- `ucs_domain` 扩展值不参与断言
- 详见 `zh_fxname_cases_expansion_notes.md`
