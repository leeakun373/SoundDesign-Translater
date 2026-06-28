# Coverage Sprint v0.1 报告

## 执行摘要

- branch: `main`
- HEAD: `33d92febf8b2369e341d8acd611ee46e1d670ddd`
- canonical 新增行数: **168**（`source=ai_reviewed_batch`, `note=coverage_sprint_v0.1`）
- AI invoked: **no**（映射由本地 sprint 规则生成，参考模拟测试 unknowns 与 AI 建议）
- promote: **yes**（本 sprint 经用户授权直接写入 `review_status=keep` runtime 行）

## 验收指标

| 指标 | Before | After | 目标 | 结果 |
| --- | ---: | ---: | --- | --- |
| pass | 29 | 119 | ≥ +25 | **+90** |
| needs_review | 121 | 31 | ≥ -25 | **-90** |
| safety_fail | 0 | 0 | 0 | **通过** |
| conflict | 0 | 0 | 0 | **通过** |

## 新增 token 按 slot 统计

| slot | 行数 |
| --- | ---: |
| object | 58 |
| action | 34 |
| source | 25 |
| detail | 24 |
| modifier | 14 |
| material | 8 |
| motion | 5 |

## Top 20 修复样例（needs_review → pass）

| ID | 测试词/短句 | 结果 | AI建议（仅review） |
| --- | --- | --- | --- |
| BOOM-001 | 吸尘器 气流 高音 哨声 | Vacuum Cleaner Air Movement High Whistle | Hoover Air Movement High Whistle |
| BOOM-002 | 飞机 掠过 深沉 共振 滤波 | Aircraft Flyby Deep Resonance Filtered | Plane By Deep Resonance Filtered |
| BOOM-003 | 乡村 牛棚 夜晚 比利时 | Countryside Cow Barn Night Belgium | Countryside Cow Barn Night Belgium |
| BOOM-004 | 海豹 呼吸 轻柔 | Harbor Seal Breathe Airy | Harbor Seal Breath Airy |
| BOOM-006 | 乌鸦 叫声 强烈 | Crow Caw Intense | Crow Caw Hard |
| BOOM-007 | 金属 弹壳 滚落 | Metal Shell Trickle Down | Metal Cartridge Case Trickle Down |
| BOOM-009 | 链条 铁板 清脆 | Chain Metal Plate Crisp | On Plate Clean |
| BOOM-010 | 背包 撞击 | Backpack Impact | Backpack |
| BOOM-011 | 阿兹特克 死亡哨 气爆 | Aztec Death Whistle Air Burst | Aztec Death Whistle Air Burst |
| BOOM-012 | 人群 乞求 平静 远处 | Crowd Beg Calm Distant | Beg Calm Far |
| BOOM-013 | 上升 飘动 冲击 | Rise Flutter Punchy | Ascending Flutter |
| BOOM-015 | 微波炉 门 关闭 闷响 | Microwave Door Close Thud | Microwave Door Clunk Close |
| BOOM-016 | 火花 碎裂 长尾 | Spark Shatter Long Tail | Spark Crumble Long |
| BOOM-017 | 塑料 工具箱 关闭 | Plastic Toolbox Close | Toolbox Plastic Close |
| BOOM-020 | 基础 打击 复古 | Basic Strike Retro | Basic Hit Old School |
| BOOM-021 | 酒精 爆燃 铝罐 | Alcohol Burst Aluminum Can | Alcohol Deflagration Aluminum Can |
| BOOM-022 | 烟花 大爆炸 | Fireworks Big Blast | Firework Big Blast |
| BOOM-024 | 卡片 拖动 转动 桌面 | Card Drag Turn On Table | Drag And Turn On Table |
| BOOM-025 | 厚玻璃 棘轮 | Thick Glass Ratchet | Glass Thick Ratchet |
| BOOM-028 | 提尔 号角 | Tyr Horns | Call Of Tyr |

## 仍然 needs_review 的 Top unknown

| unknown | 出现次数 | 备注 |
| --- | ---: | --- |
| 长 | 5 | 单字，本 sprint 不新增 keep |
| 剑 | 4 | 单字，本 sprint 不新增 keep |
| 短 | 2 | 单字，本 sprint 不新增 keep |
| 右 | 2 | 单字，本 sprint 不新增 keep |
| mana | 2 |  |
| void | 2 |  |
| 锣 | 1 | 单字，本 sprint 不新增 keep |
| 杯 | 1 | 禁止泛词 |
| 手 | 1 | 单字，本 sprint 不新增 keep |
| 大 | 1 | 单字，本 sprint 不新增 keep |
| 嘴 | 1 | 单字，本 sprint 不新增 keep |
| 劈 | 1 | 单字，本 sprint 不新增 keep |
| 刀 | 1 | 单字，本 sprint 不新增 keep |
| 小 | 1 | 单字，本 sprint 不新增 keep |
| 干 | 1 | 单字，本 sprint 不新增 keep |
| 左 | 1 | 单字，本 sprint 不新增 keep |
| 戳 | 1 | 单字，本 sprint 不新增 keep |
| 厚 | 1 | 单字，本 sprint 不新增 keep |
| 碗 | 1 | 单字，本 sprint 不新增 keep |
| 斧 | 1 | 单字，本 sprint 不新增 keep |

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

删除 `canonical_tokens.csv` 中 `note=coverage_sprint_v0.1` 的全部行，恢复 `canonical_db.py` 中 `ai_reviewed_batch`（如不需要），重跑 pytest 与模拟报告。
