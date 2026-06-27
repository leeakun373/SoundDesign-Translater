# Canonical Token Audit

- source: `E:\WorkSpace\SoundDesign Translater\fxengine\data\canonical_tokens.csv`
- passed: `true`
- total_rows: `270`
- runtime_keep_rows: `263`
- review_rows: `7`
- reject_rows: `0`
- issue_count: `3`
- error_count: `0`
- warning_count: `3`
- issue_counts: `high_risk_single_keep`=3
- conflict_count: `0`

## High-risk single-character results

| raw | row | status | rule_type | ambiguity | outcome |
| --- | ---: | --- | --- | --- | --- |
| 敲 | 111 | keep | stable_single_low_confidence | medium | runtime_keep_warning |
| 蹭 | 252 | keep | stable_single_low_confidence | medium | runtime_keep_warning |
| 划 | 254 | keep | stable_single_low_confidence | medium | runtime_keep_warning |
| 打 | 255 | review | ambiguous_single | high | excluded_from_runtime |
| 击 | 256 | review | suffix_only | high | excluded_from_runtime |
| 碰 | 257 | review | ambiguous_single | high | excluded_from_runtime |
| 响 | 258 | review | weak_token | high | excluded_from_runtime |
| 动 | 259 | review | weak_token | high | excluded_from_runtime |
| 甩 | 260 | review | ambiguous_single | high | excluded_from_runtime |
| 摔 | — | — | — | — | not_present |
| 晃 | — | — | — | — | not_present |
| 震 | — | — | — | — | not_present |
| 抖 | — | — | — | — | not_present |
| 滚 | — | — | — | — | not_present |
| 转 | — | — | — | — | not_present |
| 开 | — | — | — | — | not_present |
| 关 | — | — | — | — | not_present |
| 破 | — | — | — | — | not_present |
| 裂 | — | — | — | — | not_present |
| 碎 | — | — | — | — | not_present |

## Issues

| severity | code | rows | raw | message |
| --- | --- | --- | --- | --- |
| warning | high_risk_single_keep | 111 | 敲 | high-risk single-character alias is active at runtime |
| warning | high_risk_single_keep | 252 | 蹭 | high-risk single-character alias is active at runtime |
| warning | high_risk_single_keep | 254 | 划 | high-risk single-character alias is active at runtime |
