# SD FXName Mode Boundary 0.1 — 综合 Hardening 报告

- 生成时间：2026-06-25
- 阶段：**SD FXName Mode Boundary 0.1**
- 入口文档：[docs/FXNAME_MODE_BOUNDARY.md](../docs/FXNAME_MODE_BOUNDARY.md)

---

## 1. 修改摘要

本阶段在**不修改 UCSRenamer**、**不破坏 General 普通翻译**的前提下，为 SoundDesign Translater 建立 **General / FXName** 显式模式边界，并接入 GUI / HTTP API / 回归测试。

| 区域 | 变更 |
|------|------|
| `engine.py` | 新增 `TaskMode`（`general` / `fxname`）；`translate(task_mode=…)` 默认 `fxname`；`translate_fxname()` / `translate_general()` 封装入口；FXName 路径集成 `evaluate_fx_output` + `accept_nllb_fx_candidate` 脏短语过滤 |
| `app.py` | 任务选择器 **FXName / 音效命名**（默认）与 **General / 普通翻译**；质量区展示 Quality / Issues；Copy Result 按钮；中英混合文案 |
| `service/server.py` | `POST /translate` 支持 `task_mode`（默认 `fxname`） |
| `client/python/client.py` | `translate(..., task_mode="fxname")` |
| `tools/evaluate_fxname_quality.py` | 显式 `task_mode=fxname` |
| `tests/test_fxname_mode_boundary.py` | 模式边界回归（新增） |
| `docs/FXNAME_MODE_BOUNDARY.md` | 全入口梳理文档（新增） |

**未修改：** UCSRenamer、英→中文件名路径、`glossary/build_glossary.py` 等补词工具。

---

## 2. 模式边界说明

```
用户选择 / API task_mode
        │
        ├─ fxname（默认）+ 中文 + sentence + pro
        │     → compose_zh_to_en → slot 组装 → validate + fx_quality
        │     → NLLB 仅补 unknown 片段，accept_nllb_fx_candidate 拒绝脏短语
        │
        ├─ general + 中文 + sentence + pro
        │     → segment_for_translation + NLLB（旧句子逻辑）
        │
        └─ filename / 英→中
              → translate_filename（两种 task_mode 相同）
```

**核心原则：** FXName 模式**不再把整句 NLLB sentence output 当作 gold**；脏短语如 `Get Out Of Here`、`Oh My God`、`Was Knocked` 在 hybrid fallback 阶段被拒绝。

---

## 3. 质量指标（`tools/evaluate_fxname_quality.py`，42 用例，`task_mode=fxname`）

| 指标 | 数值 |
|------|------|
| total cases | 42 |
| pass | 37 (88.1%) |
| needs_review | 5 |
| fail | 0 |
| bad_phrase_count | **0** |
| rejected_nllb_count | 0（输出侧无脏短语残留） |
| unknown_zh_count | 4 |
| mixed_residue_count | 0 |
| empty_count | 0 |
| average_output_tokens | 3.1 |

详细 CSV/MD：`tests/results/fxname_quality_latest.csv`、`tests/results/fxname_quality_latest.md`

---

## 4. Before / After 重点样本

| 输入 | Before（问题） | After（FXName mode） | Quality |
|------|----------------|----------------------|---------|
| 塑料 盒掉 落 | `Plastic Box Get Out Of Here It S Down` | `Plastic Box Drop` | needs_review（spacing_suspect，输出正确） |
| 金属 门撞 击 | `Metal Door Was Knocked Knock` | `Metal Door Impact` | pass |
| 布帘拉动 | `Cloth Pull Oh My God Moving` | `Cloth Curtain Pull` | pass |
| 打磨 | 可能过度扩展 / 低信息 | `Sand` | pass（engine validate: low_information） |
| 杯子掉落打碎 | — | `Cup Drop Shatter` | pass |
| 纸袋撕裂 | — | `Paper Bag Tear` | pass |
| door 推开 wood | — | `Wood Door Push Open` | pass |
| exterior 混响 room tone | — | `Exterior Reverberant Room Tone` | pass |
| 塑料盒掉落 | 脏短语风险 | `Plastic Box Drop` | pass |
| 打开关闭门 | 缺 Door | `Door Open Close` | needs_review（unknown_zh） |

**脏短语三类样本（evaluate_fx_output 门禁）全部 fail 拦截，不再出现在 FXName 输出：**

- `Plastic Box Get Out Of Here It S Down`
- `Metal Door Was Knocked Knock`
- `Cloth Pull Oh My God Moving`

---

## 5. 测试结果

### pytest `tests/ -q`

| 结果 | 数量 |
|------|------|
| passed | 21 |
| failed | 2 |
| 失败用例 | `test_fxname_core_hardening.py::test_compose_good_cases`、`test_engine_good_outputs`（`打开关闭门` 缺 `Door` token — 核心 compose 词典问题，非本阶段边界回归） |

### 模式边界专项 `tests/test_fxname_mode_boundary.py`

**8/8 PASS** — General 可运行、FXName 有 quality debug、默认 task_mode=fxname、bad phrase 检测、mixed input 走 FX pipeline。

### GUI smoke

`python -c "import app"` — **OK**（模块可加载；完整窗口需本地 `pythonw app.py`）

### 质量 Harness

`python tools/evaluate_fxname_quality.py` — **完成**，见第 3 节。

---

## 6. Remaining issues

### 词典 / compose 还不够

- `打开关闭门` → `Open Close`（compose 未拆出「门」→ `Door`）；引擎输出 `Door Open Close` 但仍有 `unknown_zh`
- `门打开` / `门关闭` → needs_review（`unknown_zh`）
- `B00M 风格 木门滑开` → 多余 token `G B00m Wind`（风格前缀处理）

### 需人工 review

- spacing fuzz 输入（如 `塑料 盒掉 落`）输出正确但标记 `spacing_suspect`
- 单字动作 `打磨` → `Sand`（信息量少，engine `low_information`）
- `连发` 等枪械类短词需继续观察

### NLLB fallback 被拒绝（保护性，非 bug）

- hybrid 路径中 `accept_nllb_fx_candidate` 拒绝口语/幻觉片段，debug 含 `nllb_rejected` / `rejected_candidates`
- 用户可在 GUI Issues 区看到 **Rejected NLLB phrase / 已过滤脏短语**

---

## 7. 下一轮建议

1. **补词典：** `打开门`/`关闭门`/`门` 组合模式，修复 `打开关闭门` compose 缺 Door。
2. **统一质量门禁：** 将 `validate_fx_name` 与 `evaluate_fx_output` 的 issue 命名对齐，减少 GUI 双轨展示。
3. **HTTP 文档：** 在 README 中注明 `task_mode` 参数及默认值 `fxname`。
4. **UCS 集成：** `examples/ucs_renamer_demo.py` 显式传 `task_mode=fxname`（当前依赖 HTTP 默认）。
5. **继续 hardening：** 跑 `evaluate_fxname_quality.py --fuzz 20` 扩大空格变异覆盖。

---

## 8. 交付核对

| 项 | 状态 |
|----|------|
| 未改 UCSRenamer | ✅ |
| 未破坏 General 普通翻译 | ✅（`task_mode=general` 走 segment+NLLB） |
| FXName 不信任整句 NLLB | ✅（compose 优先 + candidate 拒绝） |
| GUI General / FXName 模式开关 | ✅ |
| 质量展示 Quality / Issues | ✅ |
| 默认模式 FXName | ✅（引擎 + GUI + HTTP） |
| bad_phrase_count = 0 | ✅（42 用例实测） |
