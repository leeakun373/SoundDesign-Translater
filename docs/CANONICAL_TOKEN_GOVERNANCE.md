# Canonical Token 词表治理规则

> 记录日期：2026-06-28  
> 关联数据：`fxengine/data/canonical_tokens.csv`  
> 关联工具：`python -m fxengine.canonical_audit`（只读 QA）

---

## 1. 核心结论

`canonical_tokens.csv` **不是普通中英词典**。

它是 **「中文声音命名输入习惯 → 专业 FXName token」** 的规则表：把用户在 FXName 输入框里会打的中文片段，映射到可检索、可组装的英文 canonical token。

---

## 2. 命中策略（已定）

采用最稳方案，优先级链如下：

```text
phrase rule  >  stable single-char rule  >  review_required  >  ignore / weak token
```

对应原则：


| 层级               | 含义                      |
| ---------------- | ----------------------- |
| **短语优先**         | 多字组合比单字更稳定，优先命中         |
| **稳定单字兜底**       | 80%+ 语境下含义唯一的单字可入主表     |
| **模糊单字进 review** | 一词多义的单字不直接映射，等短语规则或人工确认 |
| **弱信息词不直接翻译**    | 「响」「动」等结果词 / 泛化词不进主表    |


---

## 3. 词表分四类，不要平等进主表

### A. 主表：稳定 alias

可直接写入 `canonical_tokens.csv`，`review_status=keep`。

```csv
raw,canonical,slot,priority,rule_type,review_status,note
刮,Scrape,action,90,stable_single,keep,稳定单字
刮擦,Scrape,action,100,phrase,keep,大面积粗糙刮擦
拖,Drag,action,90,stable_single,keep,稳定单字
拖动,Drag,action,100,phrase,keep,
滑,Slide,action,90,stable_single,keep,稳定单字
滑开,Slide Open,action,100,phrase,keep,
撞,Impact,action,80,stable_single,keep,声音语境默认撞击
撞击,Impact,action,100,phrase,keep,
砸,Impact,action,75,stable_single,keep,默认高力度 Impact
摩擦,Friction,action,100,phrase,keep,默认物理摩擦状态
```

### B. 低置信主表：能用，但要标记

可进主表，但 `rule_type` 带 `_low_confidence` 后缀；UI 可据此降低 confidence 展示。

```csv
raw,canonical,slot,priority,rule_type,review_status,note
敲,Knock,action,65,stable_single_low_confidence,keep,可能需要 Tap/Knock 区分
晃,Shake,motion,70,stable_single_low_confidence,keep,松动物件可能应为 Rattle
剐蹭,Scuff,action,75,phrase_low_confidence,keep,轻微碰擦默认 Scuff
蹭,Rub,action,70,phrase_low_confidence,keep,来回接触默认 Rub
```

### C. Review 表：不要直接进主表

这些 **不要** 直接映射到 canonical；应进入 `canonical_token_candidates.csv` 或 `review_required.csv`，而非正式主表。

```csv
raw,canonical,slot,priority,rule_type,review_status,note
打,,action,0,ambiguous_single,review,Hit/Knock/Fire/Play 都可能
击,,action,0,suffix_only,review,通常是组合词后缀
碰,,action,0,ambiguous_single,review,Touch/Bump/Impact/Clink 都可能
响,,unknown,0,weak_token,review,结果词，不是动作
动,,unknown,0,weak_token,review,信息量太低
甩,,motion,0,ambiguous_single,review,Swing/Flick/Whip/Flap 取决于对象
```

### D. Phrase rules：专门解决歧义词

单字不进主表，但 **短语可以进** —— 这是解决「中文一词多义」的关键。

```csv
raw,canonical,slot,priority,rule_type,review_status,note
打门,Door Knock,action,95,phrase,keep,
砸门,Door Bang,action,90,phrase,keep,
敲门,Door Knock,action,100,phrase,keep,
打鼓,Drum Hit,action,95,phrase,keep,
打枪,Gun Fire,action,95,phrase,keep,
碰杯,Glass Clink,action,100,phrase,keep,
轻碰,Bump,action,80,phrase,keep,
甩衣服,Cloth Flap,motion,90,phrase,keep,
甩鞭,Whip Crack,motion,95,phrase,keep,
金属响,Metal Resonance,detail,80,phrase,keep,
铃响,Ring,action,90,phrase,keep,
```

---

## 4. Scrape 组最终规则（已定）


| 中文输入         | canonical              | 说明                                                         |
| ------------ | ---------------------- | ---------------------------------------------------------- |
| 刮 / 刮擦 / 刮过  | Scrape / Scrape Across | 主路径                                                        |
| 摩擦           | Friction               | 物理摩擦状态                                                     |
| 蹭 / 来回蹭      | Rub                    | 来回接触                                                       |
| 剐蹭 / 轻蹭 / 磨到 | Scuff                  | 轻微碰擦                                                       |
| 划 / 划痕       | Scratch                |                                                            |
| 划过           | —                      | Swipe / Slide Across / Pass By；**不进单一主表**，先做 phrase review |


推荐落表：

```csv
raw,canonical,slot,priority,rule_type,review_status,note
刮,Scrape,action,90,stable_single,keep,
刮擦,Scrape,action,100,phrase,keep,
刮过,Scrape Across,action,85,phrase,keep,
摩擦,Friction,action,100,phrase,keep,
来回摩擦,Rub,action,90,phrase,keep,
蹭,Rub,action,70,stable_single_low_confidence,keep,
来回蹭,Rub,action,90,phrase,keep,
剐蹭,Scuff,action,85,phrase,keep,
轻蹭,Scuff,action,85,phrase,keep,
划,Scratch,action,75,stable_single_low_confidence,keep,
划痕,Scratch,action,90,phrase,keep,
划过,,motion,0,ambiguous_phrase,review,
```

---

## 5. 推荐 CSV 结构

当前 `canonical_tokens.csv` 已有：`raw`, `canonical`, `slot`, `lang`, `priority`, `tags`, `note`。

治理字段扩展目标：

```csv
raw,canonical,slot,lang,priority,rule_type,review_status,ambiguity,tags,source,note
```


| 字段              | 作用                                                                                                                                                             |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `raw`           | 用户会输入的词                                                                                                                                                        |
| `canonical`     | 输出到 FXName 的英文 token；review 项可为空                                                                                                                               |
| `slot`          | `action` / `material` / `object` / `motion` / `detail` / `modifier` / `source`                                                                                 |
| `lang`          | 输入语言（`zh` / `en`）                                                                                                                                              |
| `priority`      | 命中优先级；同 alias 冲突时高者胜                                                                                                                                           |
| `rule_type`     | `phrase` / `stable_single` / `stable_single_low_confidence` / `phrase_low_confidence` / `ambiguous_single` / `ambiguous_phrase` / `suffix_only` / `weak_token` |
| `review_status` | `keep` / `review` / `reject`                                                                                                                                   |
| `ambiguity`     | `low` / `medium` / `high`                                                                                                                                      |
| `tags`          | 主题标签，如 `scrape` / `impact` / `door` / `cloth`                                                                                                                  |
| `source`        | `manual` / `ai_candidate` / `boom_mined`                                                                                                                       |
| `note`          | 为什么这么定                                                                                                                                                         |


---

## 6. 维护方式

以后不要问「这个中文是什么意思」，而要问：

> **这个词在我的 FXName 输入里，是否 80% 都应该输出同一个英文？**


| 答案         | 处理方式     | 示例                                                                |
| ---------- | -------- | ----------------------------------------------------------------- |
| **是**      | 进主表      | `刮擦,Scrape,action,100,phrase,keep,low,scrape,manual,`             |
| **不是**     | 进 review | `打,,action,0,ambiguous_single,review,high,hit/knock/fire,manual,` |
| **只有短语稳定** | 单字不进，短语进 | `打门,Door Knock,…` / `打枪,Gun Fire,…`                               |
| **信息量太低**  | 弱 token  | `动,,unknown,0,weak_token,review,high,generic,manual,`             |


---

## 7. 下一步：词表 QA 流程

**不要** 继续凭空扩 1000 条。应先建立 QA 流程：

### 7.1 从现有主表扫描（当前约 248 条）

找出：

- 单字条目
- 一个 `raw` 对应多个 `canonical`
- `review_status` 缺失
- `priority` 缺失
- 低置信词

### 7.2 分类处置


| 分类            | 含义                       |
| ------------- | ------------------------ |
| `keep`        | 保留在主表                    |
| `review`      | 移入 review / candidates 表 |
| `reject`      | 删除或标记拒绝                  |
| `phrase_only` | 单字移除，仅保留短语规则             |


### 7.3 对 review 项补 phrase rules

优先处理高风险单字：

```text
打  击  碰  响  动  甩  敲  蹭  划  摔  晃  震  抖  滚  转  开  关  破  裂  碎
```

### 7.4 工具落地目标

让自动化把上述判断固化为：

- `rule_type`
- `review_status`
- `ambiguity`
- `priority`
- **QA report**（结构化 JSON，非零 exit 表示有问题）

现有 `python -m fxengine.canonical_audit` 已覆盖 duplicate / conflict / invalid field 等；后续扩展上述治理字段校验。

---

## 8. 维护原则（一句话）

> **稳定单字可以收；宽泛单字不收；短语优先；宁可 unknown/review，不要错翻；翻译不好优先补词表，不改代码。**

---

## 9. 与现有代码的关系


| 组件                                   | 当前状态                                                               |
| ------------------------------------ | ------------------------------------------------------------------ |
| `fxengine/data/canonical_tokens.csv` | 主表，248 行；尚无 `rule_type` / `review_status` / `ambiguity` / `source` |
| `fxengine/canonical_db.py`           | 最长 alias 匹配 + priority 决胜                                          |
| `fxengine/canonical_audit.py`        | 只读 QA：重复 alias、冲突映射、非法字段                                           |
| `canonical_token_candidates.csv`     | **待建** — Review 表候选                                                |
| `review_required.csv`                | **待建** — 需人工确认的条目                                                  |


扩展 schema 时：先更新本文档与 audit 规则，再批量迁移现有行，最后补 phrase rules 与 QA report。