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

## Batch 0 — Dry-run Promote Planner（未来）

**目标：** 只规划，不写主表。

| 项 | 说明 |
|----|------|
| 输入 | `ai_alias_candidates_decision_recommendations.csv` |
| 过滤 | 仅 `accept_candidate` |
| 输出 | `promote_plan.csv`（planned rows + batch id + hash snapshot） |
| 主表 | **不改** `canonical_tokens.csv` |

`promote_plan.csv` 建议列：

- raw, canonical, slot, lang, priority, rule_type, review_status（目标 keep）, source, note, batch_id, decision_reason, canonical_sha256_before

---

## Batch 1 — 最安全 6 条（未来）

**目标：** 首次真实 promote 的候选集（人工确认后）。

仅包含当前 v0.1 `accept_candidate`：

| raw | canonical | slot |
|-----|-----------|------|
| 摩擦声 | Friction | action |
| 擦蹭声 | Friction | action |
| 磨蹭声 | Friction | action |
| 表面摩擦音 | Friction | action |
| 铁链 | Chain | object |
| 锁链 | Chain | object |

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
