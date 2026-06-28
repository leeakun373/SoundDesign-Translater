# AI Alias Workflow

> 记录日期：2026-06-28  
> 当前版本：v0.1（Decision Recommendations 已完成；Promote 未启用）

本文描述 **AI alias candidate** 从 BOOM evidence 到 decision recommendation 的完整流水线。  
所有中间产物都是 **review artifact**；只有未来显式 promote 才能把行写入 `canonical_tokens.csv` 且设为 `keep`。

---

## 流程总览

```text
A. Evidence          → BOOM 语料证据
B. Prompt Pack       → 人工审过的 AI 提示包
C. AI Import         → AI 输出导入为 review CSV
D. Intake            → 分批审查队列
E. Decision          → accept / needs_review / reject 建议
F. Promote           → 【未启用】未来升格为 keep
```

每阶段结束必须汇报：**AI invoked / promote / canonical changed**（见 [PROJECT_INVARIANTS.md](PROJECT_INVARIANTS.md)）。

---

## A. Evidence 阶段

**目的：** 从 BOOM metadata 提取可审查证据，不修改 runtime 主表。

### 主要工具

```powershell
python tools/build_boom_candidate_evidence.py
python tools/expand_boom_evidence_examples.py   # 可选：扩展示例并重打分
```

### 主要输出

| 文件 | 说明 |
|------|------|
| `exports/boomone_candidates/candidate_evidence.csv` | 候选证据主表 |
| `exports/boomone_candidates/expanded_examples.csv` | 扩展示例行 |
| `reports/boomone_candidate_evidence_report.md` | evidence 汇总报告 |
| `reports/boom_evidence_qa_report.md` | QA 标记报告 |

### 阶段约束

- AI invoked: **no**
- promote: **no**
- canonical changed: **no**
- BOOM 字段仅作 evidence；`canonical_guess` 不是 final token

### 前置依赖

- `data/boomone/boomone_records.sqlite`（由 `tools/export_boomone_corpus.py` 生成）
- `exports/boomone_mining/`（由 `tools/mine_boomone_tokens.py` 生成）

---

## B. Prompt Pack 阶段

**目的：** 把 evidence 中 `approved_for_ai=yes` 的项，整理成 **经人工 review 的** JSONL 提示包。

### 主要工具

```powershell
python tools/review_ai_prompt_candidates.py      # 生成 reviewed_prompt_candidates.csv
python tools/build_ai_alias_prompt_pack.py       # 按 mode 生成 JSONL pack
```

### 主要输出

| 文件 / 目录 | 说明 |
|-------------|------|
| `exports/ai_alias_prompt_pack/reviewed_prompt_candidates.csv` | 人工审过的 prompt 候选清单 |
| `exports/ai_alias_prompt_pack/reviewed_new_candidate/` | new_candidate 模式 JSONL pack |
| `exports/ai_alias_prompt_pack/reviewed_alias_expansion/` | alias_expansion 模式 JSONL pack |
| `reports/ai_alias_prompt_pack_*_report.md` | 各 mode 构建报告 |

### 禁止使用旧 pack

**禁止** 直接使用未审过的旧目录：

- ~~`exports/ai_alias_prompt_pack/new_candidate/`~~
- ~~`exports/ai_alias_prompt_pack/alias_expansion/`~~

必须走 **`reviewed_new_candidate/`** 与 **`reviewed_alias_expansion/`** 路径。

### 阶段约束

- AI invoked: **no**（仅构建 prompt，不调用模型）
- promote: **no**
- canonical changed: **no**

---

## C. AI Import 阶段

**目的：** 把 AI 生成的 alias 提案导入为 **只读 review CSV**。

### 主要工具

```powershell
# dry-run（无外部 AI，用内置 mock 验证流水线）
python tools/import_ai_alias_candidates.py --dry-run

# real import（读取人工粘贴/保存的 AI 输出 CSV）
python tools/import_ai_alias_candidates.py --import-csv exports/ai_alias_prompt_pack/raw_ai_alias_output.csv
```

### 主要输入 / 输出

| 文件 | 方向 | 说明 |
|------|------|------|
| `exports/ai_alias_prompt_pack/raw_ai_alias_output.csv` | 输入 | AI 原始输出（人工保存） |
| `tools/import_ai_alias_candidates.py` | 工具 | 校验 + 规范化 + 去重 |
| `exports/ai_alias_prompt_pack/ai_alias_candidates_review_real.csv` | 输出 | 导入后的 review 表 |
| `reports/ai_alias_candidates_review_real_report.md` | 输出 | 导入报告 |

### 输出行约束（硬规则）

每条 accepted 行必须满足：

- `review_status=review`（**不得** `keep`）
- `source=ai_candidate`
- `priority=0`
- `rule_type=alias`

### 阶段约束

- AI invoked: **yes**（real import 场景；dry-run 为 no）
- promote: **no**
- canonical changed: **no**

---

## D. Intake 阶段

**目的：** 把导入 CSV 转为带 batch / risk / action 的审查队列。

### 主要工具

```powershell
python tools/build_ai_alias_candidate_review_intake.py
```

### 主要输入 / 输出

| 文件 | 说明 |
|------|------|
| `exports/ai_alias_prompt_pack/ai_alias_candidates_review_real.csv` | 输入 |
| `exports/ai_alias_prompt_pack/ai_alias_candidates_review_intake.csv` | 输出 |
| `reports/ai_alias_candidates_review_intake_report.md` | 报告 |

### 新增列

| 列 | 说明 |
|----|------|
| `review_batch` | `batch_safe` / `batch_caution` / `batch_weapon` |
| `review_risk` | `low` / `medium` / `high` |
| `review_action` | 初始值 **`pending`** |
| `review_reason` | 特殊 canonical 或 batch 默认原因 |

### 阶段约束

- AI invoked: **no**
- promote: **no**
- canonical changed: **no**

---

## E. Decision 阶段

**目的：** 基于 intake 队列生成 **决策建议**，仍不 promote、不改主表。

### 主要工具

```powershell
python tools/recommend_ai_alias_candidate_decisions.py
```

### 主要输入 / 输出

| 文件 | 说明 |
|------|------|
| `exports/ai_alias_prompt_pack/ai_alias_candidates_review_intake.csv` | 输入 |
| `exports/ai_alias_prompt_pack/ai_alias_candidates_decision_recommendations.csv` | 输出 |
| `reports/ai_alias_candidates_decision_recommendations_report.md` | 报告 |

### `decision_recommendation` 取值

| 值 | 含义 |
|----|------|
| `accept_candidate` | 低风险 safe batch，可作为未来 promote 第一批候选 |
| `needs_review` | 需人工确认；**不得** 自动 promote |
| `reject_candidate` | 明确违反禁词 / 规则（当前 v0.1 可能为 0） |

### 附加列

- `decision_reason` — 分号分隔的原因码
- `conflict_group` — 同一 raw 映射多个 canonical 时分配（例如 `raw_conflict_001`）

### v0.1 当前结果（参考）

- accept_candidate: 6
- needs_review: 42
- reject_candidate: 0
- raw conflict: 1 组（碰击声 → Hit / Impact）
- promote: **no**
- keep: **no**

### 阶段约束

- AI invoked: **no**
- promote: **no**
- canonical changed: **no**

---

## F. Promote 阶段（尚未实现 / 尚未启用）

**目的（未来）：** 把 `accept_candidate` 且人工确认的行升格为 `review_status=keep` 并写入 `canonical_tokens.csv`。

当前 **不得** 执行 promote。详见 [BATCH_PROMOTION_PLAN.md](BATCH_PROMOTION_PLAN.md)。

硬规则预览：

- 必须小批量
- 只允许 `accept_candidate`
- `needs_review` 不得自动 promote
- `batch_weapon` 不得自动 promote
- 必须先输出 patch / report，再由用户确认
- 每个 batch：before/after hash、rollback note、pytest、report

---

## 命令速查（完整链路）

```powershell
# 0. 基线
git status
python -m pytest tests/ -q

# A. Evidence
python tools/build_boom_candidate_evidence.py

# B. Prompt Pack
python tools/review_ai_prompt_candidates.py
python tools/build_ai_alias_prompt_pack.py --mode new_candidate
python tools/build_ai_alias_prompt_pack.py --mode alias_expansion

# C. AI Import（人工完成 AI 调用并保存 raw_ai_alias_output.csv 后）
python tools/import_ai_alias_candidates.py --import-csv exports/ai_alias_prompt_pack/raw_ai_alias_output.csv

# D. Intake
python tools/build_ai_alias_candidate_review_intake.py

# E. Decision
python tools/recommend_ai_alias_candidate_decisions.py

# F. Promote — 不要运行（未启用）
```

---

## 相关文档

- [PROJECT_INVARIANTS.md](PROJECT_INVARIANTS.md)
- [AI_ALIAS_REVIEW_RULES.md](AI_ALIAS_REVIEW_RULES.md)
- [LOCAL_AI_AGENT_PLAYBOOK.md](LOCAL_AI_AGENT_PLAYBOOK.md)
- [BATCH_PROMOTION_PLAN.md](BATCH_PROMOTION_PLAN.md)
