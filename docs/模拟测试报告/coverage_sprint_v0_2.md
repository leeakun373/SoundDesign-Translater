# Coverage Sprint v0.2 报告

## 执行摘要

- branch: `main`
- HEAD: `e55166a268d9c9aecb7f1170a24509f1e0ce4cac`
- canonical 新增行数: **126**（`source=ai_reviewed_batch`, `note=coverage_sprint_v0.2`）
- AI invoked: **no**（映射由本地 sprint 规则生成，参考模拟测试 unknowns 与 AI 建议）
- promote: **yes**（本 sprint 经用户授权直接写入 `review_status=keep` runtime 行）

## 验收指标

| 指标 | Before | After | 目标 | 结果 |
| --- | ---: | ---: | --- | --- |
| pass | 299 | 403 | ≥ 325 (65%) | **通过** (80.6%) |
| pass delta | — | — | — | **+104** |
| needs_review | 201 | 97 | ≤ before-100 | **-104** |
| safety_fail | 0 | 0 | 0 | **通过** |
| conflict | 0 | 0 | 0 | **通过** |

## pytest 结果

```text
........................................................................ [ 23%]
........................................................................ [ 46%]
........................................................................ [ 69%]
........................................................................ [ 92%]
........................                                                 [100%]
============================== warnings summary ===============================
C:\Users\DELL\AppData\Local\Programs\Python\Python310\lib\site-packages\requests\__init__.py:113
  C:\Users\DELL\AppData\Local\Programs\Python\Python310\lib\site-packages\requests\__init__.py:113: RequestsDependencyWarning: urllib3 (2.6.2) or chardet (7.4.3)/charset_normalizer (3.4.4) doesn't match a supported version!
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
312 passed, 1 warning in 54.60s
```

## 新增 token 按 slot 统计

| slot | 行数 |
| --- | ---: |
| detail | 45 |
| modifier | 35 |
| action | 15 |
| object | 15 |
| source | 8 |
| unknown | 5 |
| material | 3 |

## Top 30 修复样例（needs_review → pass）

| ID | 测试词/短句 | 结果 | AI建议（仅review） |
| --- | --- | --- | --- |
| BOOM-054 | Tasmanian 魔鬼 尖叫 低吼 Female | Tasmanian Devil Scream Growl Female | Tasmanian Devil Screech Grunt Female 01 |
| BOOM-055 | 松果 盒子 刮擦 缓慢 | Pinecone Box Scrape Slow | Pinecone Box Scrape Slow |
| BOOM-057 | Gnarly Driven Sine Drive 掠过 | Gnarly Driven Sine Drive Flyby | Gnarly Driven Sine Drive By |
| BOOM-060 | Granular Madness | Granular Madness | Granular Madness |
| BOOM-064 | Concrete Paving Slab Blanket Throw | Concrete Paving Slab Blanket Throw | Concrete Paving Slab Blanket Throw |
| BOOM-077 | Carronade | Carronade | Carronade |
| BOOM-079 | Fuse Ignite and Extinguish 中等 | Fuse Ignite And Extinguish Medium | Fuse Ignite and Extinguish Medium |
| BOOM-080 | 铃声 Upwards 缓慢 | Chime Upwards Slow | Chime Upwards Slow |
| BOOM-082 | Playful | Playful | Playful |
| BOOM-083 | Accordion Clavier Cluster Sustain | Accordion Clavier Cluster Sustain | Accordion Clavier Cluster Sustain |
| BOOM-085 | Eternal Light | Eternal Light | Eternal Light |
| BOOM-087 | Inch 轻柔 Horizontal | Inch Airy Horizontal | 60 Inch Soft Horizontal |
| BOOM-088 | iridium | Iridium | iridium |
| BOOM-091 | Snarl | Snarl | Snarl |
| BOOM-093 | Greasy Alerted | Greasy Alerted | Greasy Alerted |
| BOOM-105 | Ithaca 操作 | Ithaca Operate | Ithaca M37 Handling 1m |
| BOOM-106 | Dragunov PSL Single 射击 | Dragunov Psl Single Shot | Dragunov PSL Single Shot 01 50m |
| BOOM-116 | One Handed 撞击 轻柔 | One Handed Impact Airy | One Handed 01 Impact Soft |
| BOOM-117 | Two Handed 撞击 强烈 | Two Handed Impact Intense | Two Handed Impact Hard |
| BOOM-118 | Unequip | Unequip | Unequip |
| BOOM-126 | Progressive Gesture | Progressive Gesture | Progressive Gesture |
| BOOM-128 | Complex Filter Zaps | Complex Filter Zaps | Complex Filter Zaps |
| BOOM-133 | Rubbery Complex | Rubbery Complex | Rubbery Complex |
| BOOM-134 | Watermelon Liquid 气流 | Watermelon Liquid Air Movement | Watermelon Liquid Movement |
| BOOM-136 | Webley Mk Vi Revolver Reload 缓慢 And Dryfire | Webley Mk Vi Revolver Reload Slow And Dryfire | Webley Mk Vi Revolver Reload Slow And Dryfire |
| BOOM-138 | DP 气爆 | Dp Air Burst | DP 27 Burst 1m |
| BOOM-139 | PPD 气爆 | Ppd Air Burst | PPD 40 Burst 1m |
| BOOM-141 | Tokarev SVT Reload 缓慢 | Tokarev Svt Reload Slow | Tokarev SVT 40 Reload Slow |
| BOOM-142 | Sten Gun Mark II Mechanical 气爆 | Sten Gun Mark Ii Mechanical Air Burst | Sten Gun Mark II Mechanical Burst |
| REC-051 | STEEL BALL 摔倒 Tile Sharp 明亮 Clink | Steel Ball Fall Tile Sharp Bright Clink | STEEL BALL Fall Tile Sharp Bright Clink |

## 剩余 Top 30 unknown

| unknown | 出现次数 | 备注 |
| --- | ---: | --- |
| 在 | 14 | 单字，不新增 keep |
| 长 | 10 | 单字，不新增 keep |
| 短 | 8 | 单字，不新增 keep |
| 铃 | 5 | 单字，不新增 keep |
| 机 | 5 | 单字，不新增 keep |
| 像 | 5 | 单字，不新增 keep |
| 嘴 | 4 | 单字，不新增 keep |
| 剑 | 4 | 单字，不新增 keep |
| 罐 | 4 | 单字，不新增 keep |
| 怪 | 4 | 单字，不新增 keep |
| 但 | 4 | 单字，不新增 keep |
| 手 | 3 | 单字，不新增 keep |
| 大 | 3 | 单字，不新增 keep |
| 锅 | 3 | 单字，不新增 keep |
| 响 | 3 | 禁止泛词 |
| 锣 | 2 | 单字，不新增 keep |
| 杯 | 2 | 禁止泛词 |
| 劈 | 2 | 单字，不新增 keep |
| 移 | 2 | 单字，不新增 keep |
| 右 | 2 | 单字，不新增 keep |
| 厚 | 2 | 单字，不新增 keep |
| 那样 | 2 |  |
| 声 | 2 | 单字，不新增 keep |
| 版 | 2 | 单字，不新增 keep |
| 打 | 2 | 禁止泛词 |
| 甩 | 2 | 禁止泛词 |
| 牛 | 1 | 单字，不新增 keep |
| 水滴 | 1 |  |
| 驴 | 1 | 单字，不新增 keep |
| 刀 | 1 | 单字，不新增 keep |

## 禁止泛词检查

- **通过**：本 sprint 未向 runtime 添加 forbidden broad token（打/碰/响/甩/摔/地/面/开/杯/管/箱）或单字 keep。

## 验证命令

```text
python -m pytest tests/ -q
python tools/build_simulated_token_boundary_report.py
python -m fxengine.canonical_audit --no-write
git diff --check
```

## Rollback

删除 `canonical_tokens.csv` 中 `note=coverage_sprint_v0.2` 的全部行，重跑 pytest 与模拟报告。
