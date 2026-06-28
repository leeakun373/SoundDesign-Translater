# CC-CEDICT 候补词典层 v0.1

> 记录日期：2026-06-28
> 实现：`glossary/cc_cedict.py`、`tools/cc_cedict_candidate_report.py`、`tests/test_cc_cedict_candidates.py`
> 数据：`glossary/sources/cc-cedict/cedict_ts.u8`（CC BY-SA 4.0，MDBG）

本文定义 **CC-CEDICT 候补词典层** 的边界与用法。它是一个**离线、只读、weak candidate** 工具层，用于 review / BOOM Mining 辅助，**不是** runtime 组件。

---

## 1. 它不是什么（硬边界）

- **不是 runtime fallback。** CC-CEDICT 不参与运行时 normalize / FXName 组装。
- **不接 Normalize。** 不修改 Normalize 默认路径，不在 `fxengine/normalizer.py` 里接 CC-CEDICT fallback。
- **不直接进 final FXName。** 任何 CC-CEDICT 候选都不会自动成为 final token。
- **不写主表。** 本工具**永不**写入 `fxengine/data/canonical_tokens.csv`。
- **不新增 runtime keep。** 不为 forbidden broad token 新增 runtime keep，不新增任何单字 keep。

这些边界与 [PROJECT_INVARIANTS.md](../PROJECT_INVARIANTS.md) 一致：runtime 主词表唯一来源是 `canonical_tokens.csv`，只有 `review_status=keep` 才能进 runtime，promote 必须显式执行。

---

## 2. 它是什么

- 一个**离线候选生成器**：输入一个简体中文 token + 可选 BOOM target，输出 weak candidate proposal。
- 只产出 `status` 为 `promote_candidate` / `review` / `blocked` 的**建议**，供人工或 BOOM Mining 流程判断。
- promote 与否，**完全**由 BOOM Mining / review 流程决定，本工具不做决定、不写 canonical。

---

## 3. 解析规则

CC-CEDICT 行格式：

```
繁體 简体 [pin1 yin1] /gloss 1/gloss 2/
```

- 用**简体中文**（第 2 段）作为 key。
- 英文释义从 `/.../.../` 中按 `/` 拆出。
- 注释行（`#` 开头）跳过。

---

## 4. 候选清洗

对每条 gloss：

1. 去掉括号说明，例如 `to ring (a bell)` → `to ring`。
2. 整条 gloss 命中以下标记则**丢弃**：`variant of` / `old variant` / `Kangxi radical` / `surname ` / `given name` / `place name` / `measure word` / `classifier` / `CL:` / `see ` / `abbr.`。
3. gloss 词数超过 `MAX_GLOSS_WORDS`（6）视为过长，丢弃。
4. 从 gloss 中抽取英文单词（仅字母），逐词过滤：
   - 长度 < 3 丢弃；
   - 命中**英文停用词**（a/an/the/to/of/for/made/used/…）丢弃；
   - 命中**过泛英文**（见下）丢弃。
5. 保留词做 title case，例如 `wardrobe` → `Wardrobe`、`wood` → `Wood`。

### 过滤的过泛英文

```
hit, beat, sound, make, noise, open, close, thing, object, item,
place, surface, ground, classifier, measure, word, particle, grammar,
surname, given, name, old, variant, kangxi, radical
```

---

## 5. 中文 token 阻断（forbidden broad / 单字）

- **所有单字 token 默认 `blocked`**，永不 `promote_candidate`。
- 显式 **forbidden broad token**（即使单字规则改变也阻断）：

```
打 碰 响 甩 摔 地 面 开 杯 管 箱
```

`blocked` 的 token 直接返回空 candidates，不做 target 匹配。

---

## 6. Target 支持判断

- 对候选 canonical 做**大小写不敏感的整词（word boundary）匹配**。
- candidate `Wood`，target `Heavy Wood Wardrobe Slide Slow Creak` → 支持。
- candidate `Wardrobe`，target 同上 → 支持。
- candidate 不在 target 中 → 不支持。

`Wood / Wardrobe / Heavy` 这类只有在 **BOOM target 支持时**才作为 weak candidate 提为 `promote_candidate`；target 不支持时只 `review`，不 promote。

---

## 7. status 语义

| status | 含义 |
|--------|------|
| `promote_candidate` | token 未被阻断，且至少一个候选被 target 支持。**仍是建议**，由 review / BOOM Mining 决定是否 promote。 |
| `review` | token 未被阻断，但无候选被 target 支持（或 CEDICT 无该词条）。 |
| `blocked` | token 是单字或 forbidden broad token，永不 promote。 |

`propose_for_target` **只输出 proposal，不写 canonical**。

---

## 8. API

`glossary/cc_cedict.py`：

- `CEDictCandidate`：`raw / canonical / confidence / source="cc_cedict" / reason / gloss`。
- `CEDictIndex`：
  - `from_file(path: Path | None = None)` — 默认加载 `glossary/sources/cc-cedict/cedict_ts.u8`。
  - `from_lines(lines)` — 用于测试的小 fixture。
  - `lookup(token)` — 返回全部 weak candidates（不按 target 过滤）。
  - `candidates_supported_by_target(token, boom_target)` — 仅返回 target 支持的候选。
  - `propose_for_target(token, boom_target)` — 返回 `token / target / status / candidates / reasons`。

---

## 9. CLI 用法

```powershell
# 单条（默认 JSON 输出）
python tools/cc_cedict_candidate_report.py --token 衣柜 --target "Heavy Wood Wardrobe Slide Slow Creak"

# markdown 输出
python tools/cc_cedict_candidate_report.py --token 衣柜 --target "Heavy Wood Wardrobe Slide Slow Creak" --format markdown

# 可选批量 CSV（列：token, target）
python tools/cc_cedict_candidate_report.py --csv my_tokens.csv
```

输出至少包含：`token / target / status / candidates / reasons`。

---

## 10. 相关文档

- [PROJECT_INVARIANTS.md](../PROJECT_INVARIANTS.md)
- [AI_ALIAS_WORKFLOW.md](../AI_ALIAS_WORKFLOW.md)
- [AI_ALIAS_REVIEW_RULES.md](../AI_ALIAS_REVIEW_RULES.md)
- [BATCH_PROMOTION_PLAN.md](../BATCH_PROMOTION_PLAN.md)
