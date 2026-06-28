# Local AI Agent Playbook

> 读者：Cursor / Codex / 本地 AI agent  
> 语气：直接、可执行

---

## 每次开始前：先读这三份文档

1. [PROJECT_INVARIANTS.md](PROJECT_INVARIANTS.md)
2. [AI_ALIAS_WORKFLOW.md](AI_ALIAS_WORKFLOW.md)
3. [AI_ALIAS_REVIEW_RULES.md](AI_ALIAS_REVIEW_RULES.md)

不要凭聊天记忆操作；以文档和代码为准。

---

## 每次开始前：先跑这两条命令

```powershell
git status
python -m pytest tests/ -q
```

- pytest 失败 → **先修测试或回滚你的改动**，不要继续改 alias 流水线
- 记录当前 branch 与 HEAD，供结束汇报

---

## 每次结束：必须汇报

复制以下清单填写：

```text
branch:
HEAD:
pytest: <passed/failed + count>
changed files: <list>
generated reports: <list>
canonical_tokens.csv changed: yes/no   ← 默认必须是 no
AI invoked: yes/no                     ← 默认必须是 no
promote: yes/no                         ← 默认必须是 no
git status: <summary>
```

---

## 禁止事项（默认）

| 禁止 | 原因 |
|------|------|
| 自行修改 `fxengine/data/canonical_tokens.csv` | 唯一 runtime 主表；只有显式 promote 或人工授权才可改 |
| 自行 promote | promote 未启用；必须 patch + 用户确认 |
| 把 `review` 改成 `keep` | AI candidate 不得进 runtime |
| 把 BOOM evidence 当作 final token | evidence ≠ canonical |
| 调用外部 AI（除非用户明确要求） | 默认 no AI |
| 使用旧 prompt pack（非 `reviewed_*` 目录） | 必须走 reviewed 路径 |

---

## 不确定时怎么做

1. **生成 report**，不要写主表
2. 把行留在 `needs_review` / `review_action=pending`
3. 在 report 里写清：raw、canonical、冲突原因、建议人工决策
4. 汇报 `canonical_tokens.csv changed: no`

---

## 允许的操作（v0.1）

- 运行 evidence / prompt pack / import / intake / decision **工具**（不 promote）
- 新增或更新 **review CSV** 与 **reports/**
- 新增 **测试** 与 **文档**
- dry-run import（`--dry-run`）验证规则

---

## AI alias 标准命令链

```powershell
# 仅当用户明确要求继续 alias 批量时
python tools/build_ai_alias_candidate_review_intake.py
python tools/recommend_ai_alias_candidate_decisions.py
```

不要跳阶段；不要从 decision CSV 直接写 canonical。

---

## 测试要求

任何改动后：

```powershell
python -m pytest tests/ -q
```

 governance 文档改动至少应通过 `tests/test_project_governance_docs.py`。

---

## 相关入口

- 仓库根 [AGENTS.md](../AGENTS.md)
- [BATCH_PROMOTION_PLAN.md](BATCH_PROMOTION_PLAN.md) — promote 未来路线（不要提前实现）
