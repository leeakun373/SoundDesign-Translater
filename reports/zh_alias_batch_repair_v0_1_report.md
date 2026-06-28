# Chinese Alias Batch Repair v0.1 Report

## Scope

This batch applies a small, manually reviewed repair set to real Chinese FXName inputs. It adds exact governed phrases and six natural aliases, plus one general connector rule. It does not use BOOM evidence as runtime truth, does not activate AI candidates automatically, and does not add broad single-character aliases such as `打` / `碰` / `响` / `甩` / `地`.

## Before / after

| status | before | after | delta |
| --- | ---: | ---: | ---: |
| total cases | 498 | 498 | 0 |
| pass | 270 | 316 | **+46** |
| partial | 122 | 113 | **-9** |
| unknown | 27 | 14 | **-13** |
| needs_review | 79 | 55 | **-24** |
| conflict | 0 | 0 | 0 |

Targets achieved:

- pass increase target `>= 20`: **achieved (+46)**
- unknown decrease target `>= 10`: **achieved (-13)**
- no new conflict: **achieved (0 -> 0)**

Baseline: `exports/alias_workbench/zh_alias_review_workbench.csv`
After: `exports/alias_workbench/zh_alias_review_workbench_v0_1.csv`

## Repair inventory

- canonical rows before: **270**
- canonical rows after: **321**
- canonical rows added: **51**
- exact phrase mappings added: **45**
- natural aliases added: **6** (`擦蹭`, `磨蹭`, `铁链`, `锁链`, `桌边`, `滑过`)
- parser/filler rules added: **1** (`又` as a connector)
- phrase/rule items added: **46** (45 phrase mappings + 1 parser rule)
- broad ambiguous single-character aliases added: **0**
- `XXX声` / `XXX音` aliases added: **0**

`鲸鱼叫声 -> Whale Call` is an exact complete-input phrase from the real-input batch; it is not a reusable suffix alias.

## Changed files

- `fxengine/data/canonical_tokens.csv`
- `glossary/zh_compose.py`
- `tools/clean_ai_alias_candidate_surfaces.py`
- `docs/AI_ALIAS_REVIEW_RULES.md`
- `docs/BATCH_PROMOTION_PLAN.md`
- `tests/fixtures/fxname_manual_cases.csv`
- `tests/test_ai_alias_surface_cleanup.py`
- `tests/test_canonical_audit.py`
- `tests/test_zh_alias_workbench.py`
- `tests/test_zh_alias_batch_repair_v0_1.py`
- `exports/alias_workbench/zh_alias_review_workbench_v0_1.csv`
- `reports/zh_alias_batch_repair_v0_1_report.md`

## Top fixed cases

| input | before | after | repair |
| --- | --- | --- | --- |
| 打字 | Typing | Keyboard Typing | phrase |
| 打雷 | Thunder | Thunder Rumble | phrase |
| 打滑轮胎 | Skid Tire | Tire Skid | phrase |
| 车轮打滑 | Wheel Skid | Tire Skid | phrase |
| 转旋钮 | _(empty)_ | Knob Turn | phrase |
| 关保险柜 | _(empty)_ | Safe Close | phrase |
| 打火机 | Fire | Lighter Click | phrase |
| 打水漂 | Water | Stone Skip Water | phrase |
| 打蛋 | _(empty)_ | Egg Whisk | phrase |
| 碰到麦架 | _(empty)_ | Mic Stand Bump | phrase |
| 碰倒玻璃杯 | Glass | Glass Cup Knock Over | compound phrase |
| 石头互碰 | Stone | Rock Clack | phrase |
| 塑料盒互碰 | Plastic Box | Plastic Box Clack | phrase |
| 金属杆相碰 | Metal Bar | Metal Rod Clank | phrase |
| 身体碰墙 | _(empty)_ | Body Bump Wall | phrase |
| 甩毛巾 | _(empty)_ | Towel Flap | phrase |
| 甩尾巴 | _(empty)_ | Tail Swing | phrase |
| 甩棍 | _(empty)_ | Stick Whoosh | phrase |
| 摔书 | _(empty)_ | Book Drop | phrase |
| 墙皮脱落 | _(empty)_ | Plaster Crumble | phrase |
| 摩擦皮革 | Friction Leather | Leather Friction | rule bug / phrase |
| 划船 | Scratch Boat | Boat Row | rule bug / phrase |
| 刮风 | Scrape Wind | Wind Gust | rule bug / phrase |
| 骨头断裂 | Bone Apart | Bone Crack | rule bug / phrase |
| 金属断裂 | Metal Apart | Metal Snap | rule bug / phrase |

Additional fixed phrases include `冰块刮擦冰砖`, `轮胎摩擦`, `敲木门`, `蹭衣服`, `石头碎裂`, `拉链拉开再拉上`, `水倒入杯中溅出`, `来回蹭地毯`, `来回摩擦毛毯`, `晃链条`, and `轻碰桌边`.

## Remaining top unknown/review tokens

The list follows the workbench convention and includes unresolved runtime unknowns plus governed review-only tokens.

| rank | token | count |
| ---: | --- | ---: |
| 1 | 响 | 15 |
| 2 | 甩 | 7 |
| 3 | 地 | 6 |
| 4 | 打 | 6 |
| 5 | 划过 | 3 |
| 6 | 管 | 3 |
| 7 | 声 | 3 |
| 8 | 碎 | 2 |
| 9 | 面 | 2 |
| 10 | 箱 | 2 |
| 11 | 墙 | 2 |
| 12 | 破 | 2 |
| 13 | 这个 | 2 |
| 14 | 翻译 | 2 |
| 15 | 是 | 2 |
| 16 | 墙皮 | 2 |
| 17 | 高 | 2 |
| 18 | 摔 | 2 |
| 19 | 碰 | 2 |
| 20 | 抖 | 2 |

These remain unresolved intentionally where context determines meaning. In particular, `响`, `甩`, `打`, `碰`, `摔`, and `抖` were not promoted to broad aliases.

## Remaining rule_bug cases

Count: **13**

| input | current | governed target / issue |
| --- | --- | --- |
| 抽屉拉开又关上 | Drawer Pull Open Close | expectation conflict: Pull vs Drawer Open Close |
| 刮擦铁板 | Scrape Iron Plate | material normalization: Iron Plate vs Metal Plate |
| 铃响 | Ring | Bell object specificity |
| 打磨金属 | Sand Metal | Metal Grind |
| 轻碰麦克风 | Bump Microphone | Mic Bump |
| 划玻璃 | Scratch Glass | Glass Scratch ordering |
| 蹭地板 | Rub Floor | Floor Scuff |
| 滑板滑行 | Skateboard Skid | Skateboard Roll |
| 锤子砸铁板 | Hammer Impact Iron Plate | Hammer Hit Metal Plate |
| 陶瓷破碎 | Ceramic Break | Ceramic Shatter |
| 布料甩动落地 | Cloth Swipe Land | Cloth Flap Drop |
| 车辆碰撞 | Vehicle Impact | Car Crash |
| 抽屉拉开又关上（duplicate governance case） | Drawer Pull Open Close | Drawer Open Close |

## Canonical hash guard

- canonical SHA256 before: `a7981f8bbed28c33038f5c5def267952ee78efec80cde5db7313f17eb1e5fe9e`
- canonical SHA256 after: `4d70796fcfb48f1b55e6080c16073d3a3f6c0082ccad441299ca02cdd88ca447`
- canonical changed: **yes**
- change authority: **user-authorized Batch Repair v0.1 manual rule write**
- AI candidate auto-promote: **no**
- promote: **no** (no existing `review` / `needs_review` / weapon / conflict row was changed to `keep`)
- AI invoked: **no**

## Rollback note

Preferred rollback after commit: revert the single `Batch repair Chinese alias real input cases` commit and regenerate the workbench.

Manual rollback before commit:

1. Remove the 51 canonical rows whose note contains `batch_repair_v0.1`.
2. Remove `又` from `FILLER_CHARS` in `glossary/zh_compose.py`.
3. Restore `橡胶轮胎摩擦` in `tests/fixtures/fxname_manual_cases.csv` to `Rubber Tire Rub`.
4. Delete the v0.1 workbench and this report.
5. Run `python -m pytest tests/ -q` and rebuild the baseline workbench.

Expected canonical SHA256 after a clean rollback: `a7981f8bbed28c33038f5c5def267952ee78efec80cde5db7313f17eb1e5fe9e`.
