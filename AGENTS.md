# Agent Entry

本地 AI agent（Cursor / Codex）处理本仓库时，按以下顺序阅读并遵守。

---

## ⭐ 当前方向（先读这段，一眼看懂现在在做什么）

本仓库现在有**两条并行的轨道**，别搞混：

### 轨道 A（主方向 / 活跃开发）：`translator/` 混合翻译引擎

- 做什么：中文 → BOOM 风格英文音效名 + 中英互译。
- 怎么做：jieba 分词 + 词典/CC-CEDICT + 本地 NLLB 兜底 + BOOM 全库风格吸附。
- 入口：`translator/api.py`；核心：`translator/fxname_mode.py`。
- 允许 NLLB/词典输出进入最终结果；**只读** `canonical_tokens.csv`，不写。
- 先读：[docs/翻译系统_大白话说明.md](docs/翻译系统_大白话说明.md)（大白话）、
  [docs/TRANSLATOR_ARCHITECTURE.md](docs/TRANSLATOR_ARCHITECTURE.md)、
  [docs/TRANSLATOR_METHODOLOGY.md](docs/TRANSLATOR_METHODOLOGY.md)。
- 维护：改 `translator/data/fx_overrides.csv`（小例外表）；
  自动表 `fx_overrides_auto.csv` 用 `python tools/mine_overrides.py` 重建。

### 轨道 B（Legacy / 受治理，保留不删）：`fxengine` canonical 治理流水线

- 旧的纯词表确定性 normalize + AI alias 审查/promote 流程。
- 下面第 1–10 节的「默认禁止 / 默认流程」**只约束轨道 B**，继续有效。
- 老 GUI（`fxengine/ui.py`）等保留作参考，未删除。

> 改翻译质量 → 走轨道 A；碰 canonical 主表 / alias promote → 守轨道 B 的规则。

---

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
