# Project Invariants

> 记录日期：2026-06-28  
> 适用范围：SoundDesign Translater / FXName 治理与 AI alias 批量流程  
> 关联主表：`fxengine/data/canonical_tokens.csv`

---

## 1. 本项目不是普通翻译器

SoundDesign Translater 的目标不是把中文或英文自由翻译成自然语言。

它的核心任务是：**把中文 / 中英混合输入，规范化为可审查、可检索、可组装的 FXName token 序列**。

- 输入：用户在 FXName 输入框里会打的中文片段、口语别名、中英混合关键词
- 输出：受治理的英文 canonical token（例如 `Impact`、`Friction`、`Chain`）
- 失败路径：无法稳定映射时，应进入 review / unknown，而不是靠 NLLB 或自由翻译硬凑 final FXName

---

## 2. Runtime 主词表唯一来源

`fxengine/data/canonical_tokens.csv` 是 **唯一 runtime 主词表**。

- 运行时 normalize / FXName 组装 **只读取** 这张表
- 其它 CSV、报告、BOOM evidence、AI 输出 **都不是** runtime 主词表
- 任何阶段都不应把 review 表、候选表、metadata 表误当作 runtime 数据源

---

## 3. 只有 `review_status=keep` 才能进 runtime

| review_status | 能否进 runtime | 说明 |
|---------------|----------------|------|
| `keep` | **是** | 经人工确认或显式 promote 后的正式 alias |
| `review` | **否** | 待审候选，只能存在于 review CSV / report |
| `reject` | **否** | 已拒绝，不得激活 |
| `ai_candidate` | **否** | AI 生成态，不得直接进入 runtime |
| `metadata_candidate` | **否** | BOOM / metadata 推断态，不得直接进入 runtime |

**硬规则：**

- `review` / `reject` / `ai_candidate` / `metadata_candidate` **都不能直接进 runtime**
- AI 只能生成 candidates（`source=ai_candidate`, `review_status=review`）
- BOOM metadata 只能作为 evidence，不能覆盖 final output

---

## 4. Unknown 中文不得靠 NLLB 或自由翻译进入 final FXName

- 主表中不存在、且 review 链未确认的 raw，normalize 结果应为 **unknown / 待审**，而不是 NLLB 直译英文
- NLLB 可用于 General 翻译路径，但 **不是** canonical token 治理的写入机制
- 不允许「模型觉得合理就写进 final FXName」

---

## 5. BOOM metadata 只能是 evidence

BOOM corpus / mining / candidate evidence 的作用：

- 提供 **record_count、field hits、examples、CatID 对齐** 等证据
- 帮助人工或 AI 决定「是否值得生成 alias candidate」
- **不能** 因为 BOOM 里出现了某词，就直接写入 `canonical_tokens.csv` 或覆盖 normalize 输出

Evidence 文件示例：

- `exports/boomone_candidates/candidate_evidence.csv`
- `exports/boomone_candidates/expanded_examples.csv`
- `reports/boomone_candidate_evidence_report.md`

---

## 6. AI 只能生成 candidates

- AI **不能** 直接写 `canonical_tokens.csv`
- AI **不能** 把 `review_status` 设为 `keep`
- AI 输出必须经过 import → intake → decision →（未来）显式 promote
- 默认 `source=ai_candidate`, `priority=0`, `review_status=review`

---

## 7. Promote 必须显式执行

Promote 是把 review 候选 **升格为 keep 行** 的唯一合法路径（除人工直接编辑主表外）。

Promote 必须满足：

1. **显式命令 / 脚本调用**（例如未来的 batch promote planner），不能隐式发生
2. **必须有测试**（pytest 全量或针对性回归）
3. **必须有报告**（before/after hash、行数、batch、rollback note）
4. **必须用户确认**（patch / report 先行，再 apply）
5. `needs_review` **不得** 自动 promote
6. `batch_weapon` **不得** 自动 promote
7. `conflict_group` **不得** 自动 promote

当前 v0.1 阶段：**promote 尚未启用**；decision 阶段 `promote=no`。

---

## 8. `canonical_tokens.csv` hash guard 必须保留

所有会触达 canonical 路径的工具（evidence、prompt pack、import、intake、decision、未来 promote）必须：

1. 在处理 **前** 记录 `canonical_tokens.csv` 的 SHA256
2. 在处理 **后** 再次计算 SHA256
3. 若 hash 变化且该阶段 **未授权** 修改主表 → **立即失败**

这是防止 review 流水线误写 runtime 主表的最后一道闸。

---

## 9. 每个阶段必须汇报的三项

无论人工还是 AI agent，每完成一个阶段，必须在 report 或会话汇报中说明：

| 字段 | 含义 |
|------|------|
| **AI invoked** | 是否调用了外部 LLM（`yes` / `no`） |
| **promote** | 是否执行了 promote（`yes` / `no`） |
| **canonical changed** | `canonical_tokens.csv` 是否被修改（`yes` / `no`） |

v0.1 AI alias pipeline 各阶段默认值：

| 阶段 | AI invoked | promote | canonical changed |
|------|------------|---------|-------------------|
| BOOM evidence | no | no | no |
| Prompt pack build | no | no | no |
| AI import | yes（若 real import） | no | no |
| Review intake | no | no | no |
| Decision recommendations | no | no | no |
| Promote（未启用） | no | no | 仅 promote 阶段允许 yes |

---

## 10. 相关文档

- [AI_ALIAS_WORKFLOW.md](AI_ALIAS_WORKFLOW.md) — 完整批量流程
- [AI_ALIAS_REVIEW_RULES.md](AI_ALIAS_REVIEW_RULES.md) — 审查与 batch 规则
- [LOCAL_AI_AGENT_PLAYBOOK.md](LOCAL_AI_AGENT_PLAYBOOK.md) — Cursor / Codex 操作手册
- [BATCH_PROMOTION_PLAN.md](BATCH_PROMOTION_PLAN.md) — 未来 promote 路线
- [CANONICAL_TOKEN_GOVERNANCE.md](CANONICAL_TOKEN_GOVERNANCE.md) — 主表治理细则
- [CANONICAL_TOKEN_WORKFLOW.md](CANONICAL_TOKEN_WORKFLOW.md) — BOOM → candidate 总览
