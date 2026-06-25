# SD FXName Quality Hardening 0.1 — Consolidation 最终报告

- 生成时间：2026-06-25
- 阶段：**SD FXName Quality Hardening 0.1 — Consolidation**
- 入口文档：[docs/FXNAME_MODE_BOUNDARY.md](../../docs/FXNAME_MODE_BOUNDARY.md)
- 质量 Harness 最新结果：`tests/results/fxname_quality_latest.csv`

---

## 1. 本轮修改摘要（三 Agent 成果整合）

| Agent 成果 | 保留内容 | 本轮收口 |
|------------|----------|----------|
| **Agent 1 — Quality Harness** | `tools/evaluate_fxname_quality.py`、`glossary/fx_quality.py`、bad phrase blacklist、`tests/test_fx_quality_evaluator.py` | 统一 issue 命名；清理历史 timestamp 报告，保留 `fxname_quality_latest.*` |
| **Agent 2 — FXName Core Hardening** | `glossary/zh_compose.py`、`glossary/fx_slots.py`、`glossary/fx_name.py`、`accept_nllb_fx_candidate`、compose/slot 管线 | 修复「打开关闭门」phrase alias；新增门短语回归测试 |
| **Agent 3 — Mode Boundary** | `TaskMode`（general/fxname）、`app.py` 任务选择器、`service/server.py` `task_mode`、`tests/test_fxname_mode_boundary.py` | 文档与 GUI issue 展示对齐统一 issue 集；`structural_issues` 与对外 `issues` 分离 |

**本轮代码改动（Consolidation）：**

- `glossary/packs/zh_fx_patterns.csv` — `打开关闭门` / `开关门` / `门打开关闭` → `Door Open Close`
- `glossary/fx_quality.py` — `normalize_fx_issue` / `normalize_fx_issues`、canonical issue 集
- `glossary/fx_name.py` — `natural_sentence` → `sentence_like_output`
- `engine.py` — 对外 `issues` 仅输出 canonical 名；`nllb_rejected` → `nllb_candidate_rejected`
- `app.py` — GUI Issues 区使用规范化 issue 名
- `tests/test_fxname_core_hardening.py` — 门短语精确回归（compose + engine）
- 删除 8 份重复的历史 `fxname_quality_20260625_01*` 报告

**未修改：** UCSRenamer、General 普通翻译路径、`glossary/build_glossary.py`。

---

## 2. General / FXName 模式边界

```
用户 / API task_mode
        │
        ├─ fxname（默认）+ 中文 + sentence + pro
        │     → normalize → compose_zh_to_en → slot 组装
        │     → validate_fx_name（structural_issues，内部）
        │     → evaluate_fx_output（canonical issues）
        │     → NLLB 仅补 unknown 片段 + accept_nllb_fx_candidate 脏短语过滤
        │
        ├─ general + 中文 + sentence + pro
        │     → segment_for_translation + NLLB 整句（保留旧逻辑）
        │
        └─ filename / 英→中
              → translate_filename（两种 task_mode 相同）
```

| UI / API 命名 | 值 | 说明 |
|---------------|-----|------|
| **FXName / 音效命名** | `fxname` | 默认；走 hardening pipeline |
| **General / 普通翻译** | `general` | 不走 FXName 质量门禁 |

---

## 3. Before / After 质量指标

### Baseline Harness（42 fixture，`task_mode=fxname`，无 fuzz）

| 指标 | Before（整合前） | After（本轮） |
|------|------------------|---------------|
| total | 42 | 42 |
| pass | 12 → 37（核心修复后） | **38** |
| needs_review | 21 → 5 | **4** |
| fail | 9 → 0 | **0** |
| bad_phrase_count | 9 → 0 | **0** |
| unknown_count | — | **3** |
| mixed_residue_count | — | **0** |
| average_output_tokens | — | **3.1** |

### Fuzz Harness（`--fuzz 10`，51 cases）

| 指标 | 结果 |
|------|------|
| total | 51 |
| pass | 38 |
| needs_review | 13（主要为 `spacing_suspect`） |
| fail | 0 |
| bad_phrase_count | **0** |

---

## 4. 重点样本 Before → After

| 输入 | Before（问题） | After | Quality |
|------|----------------|-------|---------|
| 塑料 盒掉 落 | `Plastic Box Get Out Of Here It S Down` | `Plastic Box Drop` | needs_review（`spacing_suspect`，输出正确） |
| 金属 门撞 击 | `Metal Door Was Knocked Knock` | `Metal Door Impact` | pass |
| 布帘拉动 | `Cloth Pull Oh My God Moving` | `Cloth Curtain Pull` | pass |
| 打磨 | NLLB 脏句风险 | `Sand` | pass |
| 水流 过 石头 | NLLB 碎句 | `Water Flow Over Stone` | pass |
| 打开关闭门 | `Open Close` / `Open Close Door`（缺 Door 或顺序错） | **`Door Open Close`** | **pass** |
| 杯子掉落打碎 | — | `Cup Drop Shatter` | pass |
| 纸袋撕裂 | — | `Paper Bag Tear` | pass |
| door 推开 wood | 整句 NLLB 风险 | `Wood Door Push Open` | pass |
| exterior 混响 room tone | 整句 NLLB 风险 | `Exterior Reverberant Room Tone` | pass |

**脏短语门禁（不再出现在 FXName 最终输出）：** `It S`、`Get Out Of Here`、`Oh My God`、`Was Knocked`、`How Can I Help You` 等 — `bad_phrase_count=0`。

---

## 5. 「打开关闭门」Root Cause 与修复

**Root cause：**

1. compose 最长匹配时，`打开` + `关闭` 能匹配，但尾部 `门` 因 `_is_isolated_zh_term` 在复合词内被跳过，或未命中 phrase-first；
2. 旧 alias `Open Close Door` 经 slot 组装后顺序为 action 在前，与 Boom 风格 `Door Open Close` 不一致；
3. `开关门` 被 glossary `开关→Switch` 抢先匹配，产出 `Switch` + unknown `门`。

**修复：**

在 `glossary/packs/zh_fx_patterns.csv` 增加/修正 phrase-first alias（priority 125）：

- `打开关闭门` → `Door Open Close`
- `开关门` → `Door Open Close`
- `门打开关闭` → `Door Open Close`

整句一次命中，slot 拆分为 Door（object）+ Open/Close（action），组装顺序 `Door|Open|Close`，coverage=1.0，无 `unknown_zh`。

---

## 6. Issue 命名对齐

**统一对外 issue 集（evaluator / engine / GUI / 报告）：**

`bad_phrase` · `sentence_like_output` · `unknown_zh` · `mixed_language_residue` · `empty_output` · `too_long` · `over_expanded` · `spacing_suspect` · `duplicate_token` · `nllb_candidate_rejected`

| 旧名 | 新名 |
|------|------|
| `natural_sentence` | `sentence_like_output` |
| `nllb_rejected` | `nllb_candidate_rejected` |
| `rejected_nllb_candidate:…` | `nllb_candidate_rejected` |
| `low_information` / `missing:*` / `forbidden:*` | 仅保留在 `debug.structural_issues`，不并入对外 `issues` |

实现：`glossary/fx_quality.py` 中 `normalize_fx_issues()`；`engine.py` 最终输出前规范化。

---

## 7. 测试结果

| 命令 | 结果 |
|------|------|
| `python -m pytest tests/ -q` | **26 passed**, 0 failed |
| `python tools/evaluate_fxname_quality.py` | pass 38 / needs_review 4 / fail 0 / bad_phrase_count 0 |
| `python tools/evaluate_fxname_quality.py --fuzz 10` | pass 38 / needs_review 13 / fail 0 / bad_phrase_count 0 |
| `python -c "import app; print('import app OK')"` | **import app OK** |
| `tests/test_fxname_mode_boundary.py` | 8/8 PASS（含在 pytest 内） |

---

## 8. Remaining issues（needs_review 说明）

| 输入 | 输出 | Issue | 原因 |
|------|------|-------|------|
| 门打开 | `Door Open` | `unknown_zh` | 单字 `门` 走 hybrid fallback，coverage < 1 |
| 门关闭 | `Door Close` | `unknown_zh` | 同上 |
| B00M 风格 木门滑开 | `Wood Door Slide Open G B00m Wind` | `unknown_zh` | 风格前缀 `B00M` 拆出多余 token |
| 塑料 盒掉 落 | `Plastic Box Drop` | `spacing_suspect` | 异常空格 fuzz；输出本身正确 |

**待人工审核 alias：** `B00M` / 库风格前缀剥离策略；`门打开`/`门关闭` 可考虑补 phrase alias。

**不属于 bug：** hybrid 路径拒绝的 NLLB 脏片段记入 `rejected_candidates` + `nllb_candidate_rejected`，不进入最终输出。

---

## 9. 硬性边界确认

| 项 | 状态 |
|----|------|
| 未改 UCSRenamer | ✅ |
| 未破坏 General 普通翻译 | ✅（`task_mode=general` → segment + NLLB） |
| FXName 不信任整句 NLLB | ✅（compose 优先 + `accept_nllb_fx_candidate`） |
| bad_phrase_count = 0 | ✅（42 + fuzz 51 实测） |
| 未放宽 bad phrase gate | ✅ |
| 未用 xfail/skip 掩盖失败 | ✅ |

---

## 10. 修改文件列表

- `glossary/packs/zh_fx_patterns.csv`
- `glossary/fx_quality.py`
- `glossary/fx_name.py`
- `engine.py`
- `app.py`
- `docs/FXNAME_MODE_BOUNDARY.md`
- `tests/test_fxname_core_hardening.py`
- `tests/test_fx_quality_evaluator.py`
- `tests/test_fx_name_matrix.py`
- `tools/run_smoke_real_cases.py`
- `tests/results/fxname_hardening_report.md`（本文件）
- `tests/results/fxname_quality_latest.csv` / `.md`（Harness 输出）
