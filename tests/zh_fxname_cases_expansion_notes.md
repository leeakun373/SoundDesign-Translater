# 中文 FXName 测试案例扩充说明（051–150）

> 文件：`tests/zh_fxname_governance_cases_150.csv`（001–050 与批次 1 相同，051–150 为新增）

## 1. 这些案例不是为了立即全部通过

150 条是 **失败模式暴露库**，不是验收清单。当前引擎/词表未覆盖的短语、消歧、复合动作 **应 fail**，fail 即 baseline。

## 2. 这些案例用于暴露失败模式

Runner 输出 `pass / fail / pending` 与 JSON 报告即可；**不要为了 pass 率去 patch engine / canonical / glossary**。

## 3. 当前最重要的失败模式

| 模式 | 代表 id / 输入 |
|------|----------------|
| **单字误映射** | 025–036：打 / 碰 / 响 / 动 / 甩 |
| **短语未覆盖** | 040 打枪、101 刮风、091 划火柴、124 摔门 |
| **对象消歧失败** | 046 铃响、072 链条响、073 风扇响、045 金属响 |
| **材质动作边界** | Scrape / Scratch / Scuff / Rub / Friction（104–110、006） |
| **Drop / Impact / Slam / Hit / Smash / Shatter 混淆** | 121–130 |
| **复合动作只保留第一个动词** | 003、141–150 |
| **录音元数据污染 FXName** | 批次 2 计划中的脏输入（本批暂未纳入） |

## 4. Runner 使用方式

```bash
python tools/run_zh_fxname_cases.py --csv tests/zh_fxname_governance_cases_150.csv \
  --report tests/results/zh_fxname_governance_report_150.json
python -m pytest tests/test_zh_fxname_governance_cases.py -q
```

输出 top fail cases 用于排优先级；**不要**因 fail 立即改 engine。

## 5. 后续转化路径

按 runner 高频 fail 分批处理：

1. **缺 phrase rule** → 进 `canonical_tokens.csv` 或 phrase 候选表（人工 QA 后）
2. **治理状态不够细** → 补 `review_status` / `rule_type`（见 `docs/CANONICAL_TOKEN_GOVERNANCE.md`）
3. **复合动作** → 独立 composite phrase 表，不硬编码 if/else
4. **runner 断言过严** → 修订 CSV 期望（词序容差、多选 `expected_fxname`），仍不改 engine

## 6. Runner 已知限制（不硬改核心逻辑）

| 项 | 说明 |
|----|------|
| `governance_class=result` | 061、066 等行：分类标签仅文档用，runner 只看 `test_kind`（`both`/`result`/`governance`） |
| `expected_source` | 引擎 token 仅有 `canonical_csv` / `unknown_review` 等；与 `phrase_rule` / `composite_phrase` 不一致时记 **pending**，不算 hard fail |
| `ucs_domain` | PROP / REC / PIPE / CERM 等扩展域 **不参与断言**，仅人工分组 |
| 重复输入 | 114≈001、141≈003：刻意重复，用于跨批次回归对比 |
| `must_not_contain` | 子串匹配；`OnlyOpen` 等占位 token 表示「缺后半动作」，引擎未实现时仍会 fail |

## 7. 051–150 主题分布

| 区间 | 主题 |
|------|------|
| 051–060 | 「打」同词多义消歧 |
| 061–070 | 「碰」类细分 |
| 071–080 | 「响」对象消歧 |
| 081–090 | 「甩」高风险动作 |
| 091–100 | 「划」vs Scratch / 习语 |
| 101–110 | 刮 / 蹭 / 摩擦边界 |
| 111–120 | 滑 Slide / Slip / Skid / Glide |
| 121–130 | 摔 / 砸 / 掉 / 落 |
| 131–140 | 破 / 裂 / 碎 材质特化 |
| 141–150 | 复合动作 / 动作链 |
