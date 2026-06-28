# AI Alias Review Rules

> 记录日期：2026-06-28  
> 实现参考：`tools/import_ai_alias_candidates.py`、`tools/build_ai_alias_candidate_review_intake.py`、`tools/recommend_ai_alias_candidate_decisions.py`

本文固化 v0.1 审查规则，供人工审阅与本地 AI agent 批量处理时引用。

---

## 1. 通用规则

### 1.1 必填与来源

| 规则 | 处理 |
|------|------|
| `raw` 为空 | **reject**（`missing_raw`） |
| `canonical` 为空 | **reject**（`missing_canonical`） |
| `keep` 出现在 AI 输出 | **禁止**；import 阶段应失败或拒绝 |
| `source` 必须是 `ai_candidate` | 否则不符合 AI alias 流水线 |
| `priority` 必须是 `0` | AI candidate 不得携带 runtime priority |
| `review_status` 必须是 `review` | 不得直接生成 keep |

### 1.2 去重

- **raw + canonical + slot** 组合去重（`duplicate_raw_canonical_slot`）
- **raw 已存在于 `canonical_tokens.csv`** 时跳过（`duplicate_existing_canonical_raw`）
- raw 与 canonical 同为英文且规范化后相同 → reject（`raw_equals_canonical_english`）

### 1.3 多 canonical 冲突

- 同一 **raw** 对应 **多个 canonical** → **needs_review**
- 分配 `conflict_group`（例如 `raw_conflict_001`）
- conflict_group **永不自动 promote**

v0.1 已知冲突示例：

- `碰击声` → `Hit` **与** `Impact`（`raw_conflict_001`）

### 1.4 Slot 与语义

- `slot=object` 但 raw 明显是声音事件（以「声」「响」结尾）→ **needs_review**（`object_slot_sound_event`）
- 例：`链条声`、`铁链晃动声` → Chain / object → needs_review

---

## 2. 禁词 / 危险词

### Hit

- **禁止** raw 含「命中」→ **reject_candidate**（`forbidden_hit_literal_match`）
- Hit 与 Impact / Knock / Punch 易混淆 → caution batch

### Crack

- **禁止** raw 含「裂纹」→ reject（`forbidden_raw_裂纹`）
- 材料范围过宽 → caution batch（`broad_material_spread`）

### Shot

- **禁止** shotgun / mic / 收音枪 / 麦克风语境 → reject（`forbidden_shot_microphone_context`）
- 例：「shotgun mic」「枪式麦」「麦克风」相关上下文
- `发射声` 等过宽 weapon action → needs_review（`too_broad_weapon_action`）

### Gun

- **不允许** `new_candidate` pack → reject（`gun_not_allowed_new_candidate`）
- **只能** `alias_expansion`
- `枪炮` 等过宽 weapon term → needs_review（`broad_weapon_term`）

### Single Shot

- **必须保持 phrase**，不得拆成 `Single` / `Shot` 两行 → reject（`single_shot_phrase_split`）
- 一律 `batch_weapon` / high risk

---

## 3. 特殊 canonical 规则

每个 caution / weapon canonical 有固定 `review_reason`：

| canonical | review_reason | batch |
|-----------|---------------|-------|
| Hit | `ambiguous_with_impact_knock_punch` | batch_caution |
| Squeak | `category_pollution_possible` | batch_caution |
| Crack | `broad_material_spread` | batch_caution |
| Ring | `tonal_ambience_possible` | batch_caution |
| Gun | `weapon_object_high_risk` | batch_weapon |
| Shot | `weapon_action_high_risk` | batch_weapon |
| Single Shot | `phrase_weapon_high_risk` | batch_weapon |

### Ring 附加规则

以下 raw 偏向 tonal tail / reverb，强制 needs_review：

- `余响`
- `回响声`
- `金属回荡`

原因码：`tonal_tail_or_reverb_possible`

### Hit 附加规则

- raw 含「拳击声」→ 标注 `fight_specific`（仍可能 needs_review）

---

## 4. Batch 规则

### batch_safe

**Canonicals：** Impact, Friction, Chain, Door, Drop

| review_risk | 默认 decision |
|-------------|---------------|
| low | `accept_candidate` |
| medium / high | `needs_review` |

### batch_caution

**Canonicals：** Hit, Squeak, Crack, Ring

- 默认 **needs_review**（`caution_batch_default`）
- 即使 risk=low，也不自动 accept（与 safe 不同）

### batch_weapon

**Canonicals：** Gun, Shot, Single Shot

- 默认 **needs_review**（`weapon_batch_default`）
- **永不自动 promote**

---

## 5. Decision 推荐逻辑摘要

```text
batch_safe + low risk     → accept_candidate
batch_safe + medium+      → needs_review
batch_caution             → needs_review
batch_weapon              → needs_review
conflict_group            → needs_review（叠加 raw_multi_canonical_conflict）
object + 声/响            → needs_review
forbidden 禁词            → reject_candidate
```

---

## 6. Promote 安全规则

| 条件 | promote |
|------|---------|
| batch_safe + accept_candidate | 可进入 **第一批** promote 候选（仍需人工确认） |
| batch_caution | 需要更严格报告；**不** 自动 promote |
| batch_weapon | **永不** 自动 promote |
| conflict_group | **永不** 自动 promote |
| needs_review | **不得** 自动 promote |
| reject_candidate | **不得** promote |

当前 v0.1：**promote 未启用**。见 [BATCH_PROMOTION_PLAN.md](BATCH_PROMOTION_PLAN.md)。

---

## 7. v0.1 accept_candidate 清单（6 条）

以下行在当前 decision 输出中为 `accept_candidate`，是未来 Batch 1 的首选：

| raw | canonical |
|-----|-----------|
| 摩擦声 | Friction |
| 擦蹭声 | Friction |
| 磨蹭声 | Friction |
| 表面摩擦音 | Friction |
| 铁链 | Chain |
| 锁链 | Chain |

---

## 相关文档

- [PROJECT_INVARIANTS.md](PROJECT_INVARIANTS.md)
- [AI_ALIAS_WORKFLOW.md](AI_ALIAS_WORKFLOW.md)
- [BATCH_PROMOTION_PLAN.md](BATCH_PROMOTION_PLAN.md)
