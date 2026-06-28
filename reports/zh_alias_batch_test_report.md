# Chinese Alias Batch Test Report

## Summary

- test case total: **498**
- workbench row total: **551**
- pass: **270**
- partial: **122**
- unknown: **27**
- conflict: **0**
- needs_review: **79**
- directly addable alias candidates (review rows only): **2**
- directly actionable high-confidence candidates: **0**
- candidates requiring human decision: **210**
- existing AI candidates matched by real-input gaps and not active in canonical runtime: **1**
- scanned structured files: **117**

## Unknown token top 50

| rank | token | count |
| --- | --- | --- |
| 1 | 响 | 15 |
| 2 | 打 | 10 |
| 3 | 甩 | 10 |
| 4 | 碰 | 8 |
| 5 | 地 | 6 |
| 6 | 杯 | 3 |
| 7 | 划过 | 3 |
| 8 | 墙 | 3 |
| 9 | 管 | 3 |
| 10 | 声 | 3 |
| 11 | 又 | 2 |
| 12 | 回 | 2 |
| 13 | 抖 | 2 |
| 14 | 开 | 2 |
| 15 | 摔 | 2 |
| 16 | 破 | 2 |
| 17 | 碎 | 2 |
| 18 | 面 | 2 |
| 19 | 墙皮 | 2 |
| 20 | 机 | 2 |
| 21 | 倒 | 2 |
| 22 | 互 | 2 |
| 23 | 后 | 2 |
| 24 | 翻译 | 2 |
| 25 | 这个 | 2 |
| 26 | 是 | 2 |
| 27 | 高 | 2 |
| 28 | 箱 | 2 |
| 29 | 保险箱拨轮 | 1 |
| 30 | 入 | 1 |
| 31 | 晃 | 1 |
| 32 | 车漆 | 1 |
| 33 | 地毯 | 1 |
| 34 | 表面 | 1 |
| 35 | 桌角 | 1 |
| 36 | 滚 | 1 |
| 37 | 珠 | 1 |
| 38 | 转旋钮 | 1 |
| 39 | 关保险柜 | 1 |
| 40 | 击 | 1 |
| 41 | 动 | 1 |
| 42 | 震 | 1 |
| 43 | 裂 | 1 |
| 44 | 桌边 | 1 |
| 45 | 毛毯 | 1 |
| 46 | 黑 | 1 |
| 47 | 漂 | 1 |
| 48 | 蛋 | 1 |
| 49 | 包 | 1 |
| 50 | 麦架 | 1 |

## Most common missing canonical top 30

| rank | canonical | count |
| --- | --- | --- |
| 1 | Carpet | 2 |
| 2 | Tire Skid | 2 |
| 3 | Door Slam | 2 |
| 4 | Dial Turn | 1 |
| 5 | Metal | 1 |
| 6 | Leather Friction | 1 |
| 7 | Ice Scrape | 1 |
| 8 | Into | 1 |
| 9 | Friction | 1 |
| 10 | Rattle | 1 |
| 11 | Car Paint | 1 |
| 12 | Ground | 1 |
| 13 | Bump | 1 |
| 14 | Cloth Shake | 1 |
| 15 | Roll | 1 |
| 16 | Knob Turn | 1 |
| 17 | Open | 1 |
| 18 | Close | 1 |
| 19 | Table | 1 |
| 20 | Bell | 1 |
| 21 | Scuff | 1 |
| 22 | Chalkboard | 1 |
| 23 | Lighter Click | 1 |
| 24 | Thunder Rumble | 1 |
| 25 | Keyboard Typing | 1 |
| 26 | Stone Skip Water | 1 |
| 27 | Egg Whisk | 1 |
| 28 | Metal Grind | 1 |
| 29 | Mic Stand Bump | 1 |
| 30 | Glass Cup Knock Over | 1 |

## Suggested alias candidates

| raw | canonical | slot | occurrences | next_action |
| --- | --- | --- | --- | --- |
| 桌边 | Table | object | 1 | add_alias_candidate |
| 滑过 | Slide | action | 1 | add_alias_candidate |
| 单发 | Single Shot | action | 1 | review_existing_candidate |

## Recommended next batch

No high-confidence candidate met the review-only threshold.

## Case sources

| source | case_count |
| --- | --- |
| docs/CANONICAL_TOKEN_GOVERNANCE.md | 11 |
| tests/fixtures/fxname_manual_cases.csv | 141 |
| tests/fxname_quality_cases.csv | 34 |
| tests/smoke_real_cases.csv | 151 |
| tests/zh_fxname_cases_batch2_plan.md | 11 |
| tests/zh_fxname_governance_cases_150.csv | 150 |

## Safety

- canonical_tokens_sha256_before: `a7981f8bbed28c33038f5c5def267952ee78efec80cde5db7313f17eb1e5fe9e`
- canonical_tokens_sha256_after: `a7981f8bbed28c33038f5c5def267952ee78efec80cde5db7313f17eb1e5fe9e`
- canonical changed: **no**
- AI invoked: **no**
- promote: **no**
- all decisions remain: **pending**
