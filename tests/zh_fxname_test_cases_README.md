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

## 批次

| 文件 | 内容 |
|------|------|
| `zh_fxname_governance_cases_50.csv` | 批次 1：治理四类基线 + 期望字段（已修订） |
| `zh_fxname_cases_batch2_plan.md` | 批次 2：50 条分配计划（待编写） |

## 运行

```bash
python tools/run_zh_fxname_cases.py --csv tests/zh_fxname_governance_cases_50.csv
python -m pytest tests/test_zh_fxname_governance_cases.py -q
```

报告输出：`tests/results/zh_fxname_governance_report.json`

Runner 退出码：有 fail 时为 1（pass + pending 为 0 时退出 0）。第一版 baseline 不要求 50 条全 pass。
