# Agent Entry

本地 AI agent（Cursor / Codex）处理本仓库时，按以下顺序阅读并遵守。

## 先读

1. [docs/PROJECT_INVARIANTS.md](docs/PROJECT_INVARIANTS.md)
2. [docs/AI_ALIAS_WORKFLOW.md](docs/AI_ALIAS_WORKFLOW.md)
3. [docs/AI_ALIAS_REVIEW_RULES.md](docs/AI_ALIAS_REVIEW_RULES.md)

操作细则见 [docs/LOCAL_AI_AGENT_PLAYBOOK.md](docs/LOCAL_AI_AGENT_PLAYBOOK.md)。

## 默认禁止

- 不要修改 `fxengine/data/canonical_tokens.csv`
- 不要 promote
- 不要调用外部 AI
- 不要把 `review` 改成 `keep`

## 默认流程

- 所有 alias 工作走 review CSV 与 report
- 每轮开始：`git status` + `python -m pytest tests/ -q`
- 每轮结束：汇报 branch、HEAD、pytest、changed files、reports、canonical changed / AI invoked / promote

## Promote 规划

未来批处理见 [docs/BATCH_PROMOTION_PLAN.md](docs/BATCH_PROMOTION_PLAN.md)（当前未启用）。
