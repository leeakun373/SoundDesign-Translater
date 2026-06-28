# Batch Promotion Plan

> 记录日期：2026-06-28  
> 状态：**规划文档 only — 本轮不实现 promote**

本文描述未来把 `accept_candidate` 升格为 `canonical_tokens.csv` 中 `review_status=keep` 行的批处理路线。

**当前约束：** 不要运行 promote；不要修改 `canonical_tokens.csv`。

---

## 总则

每个 batch 必须包含：

1. **before/after SHA256** — `canonical_tokens.csv` hash guard
2. **rollback note** — 如何撤销本 batch 新增行
3. **pytest** — `python -m pytest tests/ -q` 全绿
4. **report** — 行级清单、batch id、决策依据、hash、rollback

Promote 硬规则（与 [AI_ALIAS_REVIEW_RULES.md](AI_ALIAS_REVIEW_RULES.md) 一致）：

- 只允许 `decision_recommendation=accept_candidate`
- `needs_review` **不得** 自动 promote
- `batch_weapon` **不得** 自动 promote
- `conflict_group` **不得** 自动 promote
- 输出必须是 **patch / plan CSV / report**，用户确认后才 apply

---

## Batch 0 — Dry-run Promote Planner

**目标：** 只规划，不写主表。

| 版本 | 输入 | 输出 | planned_count（当前） |
|------|------|------|----------------------|
| v1 | `ai_alias_candidates_decision_recommendations.csv` | `promote_plan_batch0.csv` | 6 |
| v2 | `ai_alias_candidates_decision_recommendations_v2.csv` | `promote_plan_batch0_v2.csv` | 4 |

### Batch 0 v1 问题（已发现）

v1 曾 plan 6 条带「声 / 音」尾缀的 raw（如 `摩擦声`、`擦蹭声`）。这些更像音效描述词，不像用户实际输入 token，**不能直接 promote**。

### Batch 0 v2 路线（surface cleanup 后）

在 promote planner 之前必须跑：

1. `tools/clean_ai_alias_candidate_surfaces.py`
2. `tools/recommend_ai_alias_candidate_decisions.py`（输入 surface_cleaned，输出 v2 decisions）
3. `tools/plan_ai_alias_promotions.py`（输入 v2 decisions，输出 v2 plan）

v2 当前 plan 4 条：`擦蹭`、`磨蹭`、`铁链`、`锁链`。

| 项 | 说明 |
|----|------|
| 过滤 | 仅 `accept_candidate` + `batch_safe` + 无 conflict + 非 weapon |
| 主表 | **不改** `canonical_tokens.csv` |
| batch_id | v1=`batch0_dry_run`，v2=`batch0_dry_run_v2` |

---

## Batch 1 — 最安全候选（未来）

**目标：** 首次真实 promote 的候选集（人工确认后）。

**前提：** 必须通过 Batch 0 v2 surface cleanup，不得使用 v1 带尾缀 raw。

v2 当前首选（4 条）：

| raw | canonical | slot |
|-----|-----------|------|
| 擦蹭 | Friction | action |
| 磨蹭 | Friction | action |
| 铁链 | Chain | object |
| 锁链 | Chain | object |

v1 曾考虑但已被 surface cleanup 阻断或降级：

| 原 raw | 清洗后 | 状态 |
|--------|--------|------|
| 摩擦声 | 摩擦 | reject_surface（主表已有） |
| 表面摩擦音 | 表面摩擦 | needs_review（太描述化） |

升格后行属性建议：

- `review_status=keep`
- `source=ai_candidate`（或 promote 后改为 `promoted_v0.1` — 需单独决策）
- `priority` 按 [CANONICAL_TOKEN_GOVERNANCE.md](CANONICAL_TOKEN_GOVERNANCE.md) 设定（非 0）

---

## Batch 2 — Safe needs_review 人工确认后（未来）

**目标：** 处理 `batch_safe` 中经人工 `review_action=approve` 的 needs_review 行。

示例（需人工逐条确认）：

- `冲击声` / Impact
- `重物撞击声` / Impact
- `碰击声` / Impact 或 Hit（须先解决 conflict_group）
- `砸击声` / Impact
- `链条声` / Chain（object_slot_sound_event）
- Door / Drop 相关 needs_review 行

**前提：** conflict 已消解；不得带 `conflict_group`。

---

## Batch 3 — Caution batch（未来）

**Canonicals：** Hit, Squeak, Crack, Ring

- 需要 **更严格 report**（歧义、材料扩散、tonal 污染）
- 默认仍 **不** 自动 promote；仅人工指定条目
- Ring tonal tail（余响、回响声等）需单独决策

---

## Batch 4 — Weapon batch（未来）

**Canonicals：** Gun, Shot, Single Shot

- **只允许人工指定** 条目 promote
- **永不** 批量自动 promote
- Single Shot 必须保持 phrase canonical

---

## 每个 batch 执行检查清单（未来）

```text
[ ] 读取 decision recommendations / promote_plan
[ ] 过滤：仅 accept_candidate + 目标 batch
[ ] 确认：无 conflict_group、无 weapon 自动路径
[ ] 记录 canonical_tokens_sha256_before
[ ] 生成 patch CSV + promote report（不写主表）
[ ] 用户确认
[ ] apply patch（唯一允许改主表的步骤）
[ ] 记录 canonical_tokens_sha256_after
[ ] 编写 rollback note
[ ] python -m pytest tests/ -q
[ ] 汇报：promote=yes, canonical changed=yes, batch id
```

---

## 与现有工具的关系

- 现有 `tools/promote_token_candidates.py` 服务于 **legacy candidate CSV**，不是 AI alias v0.1 路径
- AI alias promote 应新建专用 planner / applier，或扩展 promote 工具并 **单独测试**
- Decision 阶段 `tools/recommend_ai_alias_candidate_decisions.py` 已固定 `promote=no`

---

## 相关文档

- [PROJECT_INVARIANTS.md](PROJECT_INVARIANTS.md)
- [AI_ALIAS_WORKFLOW.md](AI_ALIAS_WORKFLOW.md) — 阶段 F
- [AI_ALIAS_REVIEW_RULES.md](AI_ALIAS_REVIEW_RULES.md) — Promote 安全规则
