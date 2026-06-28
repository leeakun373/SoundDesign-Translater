# Chinese Alias Batch Repair v0.2 Report

## Scope

This batch applies a manually reviewed set of exact Chinese FXName phrases from the real-input workbench. It fixes context-dependent `响` / `甩` phrases, compound action sequences, rule bugs, and six otherwise unknown complete inputs. It does not add broad runtime aliases for `打` / `碰` / `响` / `甩` / `摔` / `地`, invoke external AI, or run promote.

The context-dependent inputs `门响`, `水管响`, `打电话`, `打包`, and `甩出去` intentionally remain review-only.

## Before / after

| status | before | after | delta |
| --- | ---: | ---: | ---: |
| total cases | 498 | 498 | 0 |
| pass | 316 | 353 | **+37** |
| partial | 113 | 102 | **-11** |
| unknown | 14 | 7 | **-7** |
| needs_review | 55 | 36 | **-19** |
| conflict | 0 | 0 | 0 |

Targets achieved:

- pass increase target `>= 25`: **achieved (+37)**
- unknown decrease target `>= 7`: **achieved (-7)**
- needs_review decrease target `>= 10`: **achieved (-19)**
- no new conflict: **achieved (0 -> 0)**

Baseline: `exports/alias_workbench/zh_alias_review_workbench_v0_1.csv`

After: `exports/alias_workbench/zh_alias_review_workbench_v0_2.csv`

## Repair inventory

- canonical rows before: **321**
- canonical rows after: **357**
- canonical rows added: **36**
- exact phrase mappings added: **35**
- exact phrase mappings updated: **1** (`铃响: Ring -> Bell Ring`)
- review-only rows added: **1** (`摔`, empty canonical, `review_status=review`)
- rows whose note contains `batch_repair_v0.2`: **37**
- parser/filler changes: **0**
- broad ambiguous single-character keep aliases added: **0**
- generic `XXX声` / `XXX音` suffix aliases added: **0**

`摔` remains non-runtime and produces no FXName. `电话铃声`, `风声呼啸`, and `欢呼声` are exact complete-input phrases, not reusable sound-suffix rules.

Global fillers such as `这个`, `是`, `翻译`, `后`, `再`, `然后`, and `来回` were evaluated but not expanded in this batch. Exact compound phrases preserve sequence semantics without globally discarding potentially meaningful text.

## Top fixed cases

| input | before | after | repair |
| --- | --- | --- | --- |
| 抽屉拉开又关上 | Drawer Pull Open Close | Drawer Open Close | compound phrase |
| 铃响 | Ring | Bell Ring | object-specific phrase update |
| 警报响 | Alarm | Alarm Ring | phrase |
| 金属片响 | Metal Plate | Metal Sheet Rattle | phrase / slot correction |
| 硬币响 | Coins | Coin Jingle | phrase |
| 链条响 | Chain | Chain Rattle | phrase |
| 风扇响 | Fan | Fan Whir | phrase |
| 肚子响 | _(empty)_ | Stomach Growl | phrase |
| 甩水 | Water | Water Flick | phrase |
| 甩刀 | Knife | Knife Whoosh | contextual phrase |
| 甩手 | Hands | Hand Whoosh | contextual phrase |
| 甩门 | Door | Door Slam | contextual phrase |
| 门打开后撞到墙 | Door Open Impact | Door Open Impact Wall | compound phrase |
| 拿起杯子放下 | Cup | Cup Pick Up Put Down | compound phrase |
| 金属盒打开合上 | Metal Box Open | Metal Box Open Close | compound phrase |
| 纸张揉皱展开 | Paper Crumple | Paper Crumple Unfold | compound phrase |
| 布料甩动落地 | Cloth Swipe Land | Cloth Flap Drop | compound phrase / rule bug |
| 陶瓷破碎 | Ceramic Break | Ceramic Shatter | material-specific phrase |
| 刮擦铁板 | Scrape Iron Plate | Metal Plate Scrape | ordering / material rule bug |
| 打磨金属 | Sand Metal | Metal Grind | action rule bug |

Additional fixed cases include `轻碰麦克风`, `划玻璃`, `蹭地板`, `滑板滑行`, `锤子砸铁板`, `车辆碰撞`, `电话铃声`, `风声呼啸`, `欢呼声`, `战场呐喊`, `僵尸呻吟`, `高跟鞋踩地`, `闪光灯充能`, `溪流潺潺`, and `电钻钻孔`.

## Remaining top unknown/review tokens

This list follows the workbench convention and includes unresolved runtime unknowns plus governed review-only tokens.

| rank | token | count |
| ---: | --- | ---: |
| 1 | 响 | 9 |
| 2 | 地 | 7 |
| 3 | 打 | 6 |
| 4 | 摔 | 5 |
| 5 | 杯 | 3 |
| 6 | 碎 | 3 |
| 7 | 划过 | 3 |
| 8 | 管 | 3 |
| 9 | 抖 | 2 |
| 10 | 开 | 2 |
| 11 | 碰 | 2 |
| 12 | 甩 | 2 |
| 13 | 破 | 2 |
| 14 | 面 | 2 |
| 15 | 墙皮 | 2 |
| 16 | 翻译 | 2 |
| 17 | 这个 | 2 |
| 18 | 是 | 2 |
| 19 | 箱 | 2 |
| 20 | 保险箱拨轮 | 1 |

The seven remaining `unknown` cases are `震`, `抖`, `破`, `裂`, `碎`, the documentation fragment `磨到`, and the deliberate unknown test input `夔魍`. None has been forced into runtime.

## Remaining needs_review

Count: **36**.

The main intentional review groups are:

- broad single tokens: `打`, `击`, `碰`, `响`, `动`, `甩`, `摔`
- context-dependent phrases: `划过水面`, `打电话`, `打包`, `膝盖碰桌子`, `门响`, `水管响`, `木板响`, `机器响`, `甩出去`, `划过空气`
- unresolved fall/break compounds: `玻璃杯摔碎`, `手机摔地`, `人摔倒`, `摔门`
- noisy or metadata-bearing discovery inputs remain review-only rather than becoming aliases

## Canonical hash guard

- canonical SHA256 before: `4d70796fcfb48f1b55e6080c16073d3a3f6c0082ccad441299ca02cdd88ca447`
- canonical SHA256 after: `e769db799302935b49fbe39a176aca7e44de1bef816c2553659f4a5041e3e1af`
- canonical changed: **yes**
- change authority: **user-authorized Batch Repair v0.2 manual rule write**
- AI candidate auto-promote: **no**
- promote: **no**
- AI invoked: **no**

## Rollback note

Preferred rollback after commit: revert the single `Batch repair Chinese alias real input cases v0.2` commit and rebuild the workbench.

Manual rollback before commit:

1. Remove the 36 newly added canonical rows whose note contains `batch_repair_v0.2`, excluding the updated `铃响` row.
2. Restore `铃响` to `Ring`, priority `90`, tags `ring`, and an empty note.
3. Restore the canonical audit counts to 321 total / 314 keep / 7 review / 321 valid.
4. Delete the v0.2 test, workbench, and this report.
5. Run `python -m pytest tests/ -q` and rebuild the v0.1 workbench.

Expected canonical SHA256 after a clean rollback: `4d70796fcfb48f1b55e6080c16073d3a3f6c0082ccad441299ca02cdd88ca447`.
