# SoundDesign Translater — FXName Engine Roadmap v0.3.1

> 目标：把 SoundDesign Translater 从“本地翻译器”升级为离线可控的 **FXName 输入法 / 音效命名引擎 / Metadata 描述助手**。
>
> 重要前提：PR #1 `00aa9ae Make FXName normalization the default` 必须先合并或等价落到 `main`。后续开发若直接在 `main` 进行，必须确保 `main` 已包含 Normalize 默认行为、unknown 不走 NLLB、BOOM suggestion 不覆盖 final output 等基线。

---

## 1. 产品边界

### 1.1 现在不做什么

暂时不接 UCSRenamer。

原因：FXName Engine 尚未稳定前，过早接入 UCSRenamer 会让职责混乱。当前项目应先独立完成：

```text
中文 / 中英混合输入
→ 干净英文 FXName
→ token review
→ preference / personal dictionary
→ description stub / suggestion stub
```

UCSRenamer 后续只负责：

```text
FXName → CatID / CreatorID / SourceID / UserData / 最终 UCS 文件名
```

### 1.2 默认模式不是 AI 生成

默认模式是 **FXName Normalize**：

```text
输入
→ token 化
→ canonical token 查找
→ 保留用户顺序
→ 清理污染
→ 标记 unknown
→ 输出 FXName
```

默认不允许：

```text
unknown → NLLB 自由翻译 → 写进 final FXName
```

### 1.3 BOOM 的位置

BOOM corpus 只能作为参考层：

- phrase hits
- confidence
- optional suggestion
- similar examples
- metadata style reference

BOOM 默认不能覆盖用户输入顺序。

---

## 2. 长期模块路线

### 2.1 FXName Normalize

最常用模式。用户按 FXName 逻辑输入中文 / 中英混合 token。

示例：

```text
金属 门 撞击 → Metal Door Impact
火箭 发射 爆炸 long tail 5m → Rocket Launch Explosion Long Tail 5m
door 推开 wood → Door Push Open Wood
```

原则：

- preserve order
- 中文查 canonical token
- 英文 Title Case
- unknown 进入 review
- 不调用 NLLB
- BOOM 只给 suggestion / confidence

### 2.2 FXName Polish

用于已有英文或半句式英文润色。

示例：

```text
metal door was heavily hit outside
→ Heavy Metal Door Impact Exterior
```

Polish 可以更主动：

- 删除句子成分
- 替换动词短语
- 做轻度重排
- 用 BOOM scorer 排序候选

但 Polish 必须和 Normalize 分开，不能污染默认路径。

### 2.3 FXName Suggest

用于自由中文描述，给多个候选。

示例：

```text
金属门被重重撞了一下，尾音比较长
→
1. Metal Door Impact Heavy Long Tail
2. Heavy Metal Door Impact Long Tail
3. Metal Door Slam Long Tail
```

Suggest 是候选生成，不是单一 final。低置信必须显示 needs_review。

### 2.4 Metadata Description

用于生成 Soundminer / BOOM 风格 description。

示例：

```text
短促偏硬的布袋撞击，带一点甩动
→ Short hard cloth bag impact with slight swipe movement.
```

Description 不是 FXName，不应复用 FXName token 排序作为最终句子。第一阶段可以只做 stub，预留 UI 和接口。

### 2.5 Personal Dictionary

用户确认一次，系统记住。

示例：

```text
kuang → Metal Impact
夔魍 → Creature
```

以后相同输入直接使用用户映射。Personal Dictionary 优先级高于 BOOM、glossary sources、模型。

### 2.6 Preferences

记录用户偏好，不要写死在代码里。

示例偏好：

- `Impact` 优先于 `Hit`
- `Long Tail` 优先于 `Long Decay`
- `5m` 是否允许进入 FXName
- 是否强制 preserve order
- BOOM 是否只做 suggestion

### 2.7 Example Retrieval

从 BOOM / 用户素材库中检索相似命名，作为参考，不直接覆盖 final。

用途：

- confidence
- suggestions
- similar examples
- metadata writing reference

---

## 3. 目标架构

新增独立核心目录，避免继续在 `engine.py` 里堆补丁：

```text
fxengine/
  __init__.py
  models.py
  tokenizer.py
  canonical_db.py
  normalizer.py
  polish.py
  suggest.py
  metadata_writer.py
  personal_dictionary.py
  preferences.py
  example_retrieval.py
  scorer.py
  diagnostics.py
```

### 3.1 数据模型

`models.py` 至少定义：

```python
@dataclass
class FXToken:
    raw: str
    text: str
    canonical: str | None
    slot: str
    source: str
    confidence: float
    status: str
    issues: list[str]
```

status 建议：

```text
ok
unknown
rejected
needs_review
ignored
```

```python
@dataclass
class FXNameResult:
    input_text: str
    output_fxname: str
    mode: str
    tokens: list[FXToken]
    quality: str
    issues: list[str]
    unknowns: list[str]
    suggestions: list[str]
    boom_confidence: float | None
    boom_suggestion: str | None
    debug: dict
```

```python
@dataclass
class MetadataResult:
    input_text: str
    description: str
    quality: str
    issues: list[str]
    source_tokens: list[FXToken]
    references: list[str]
    debug: dict
```

---

## 4. UI 原型要求

本轮 UI 目标是“能手测”，不是做复杂工作站。

推荐布局：

```text
Mode: [FXName Normalize ▼]   Preference: [Default ▼]

Input
[ 金属 门 撞击 / kuang / 火箭 爆炸 long tail 5m ]

FXName Output
[ Metal Door Impact                                      Copy ]

Token Review
Raw        Canonical       Slot        Status        Action
金属       Metal           material    ok            change
门         Door            object      ok            change
撞击       Impact          action      ok            change
kuang      —               unknown     review        map / keep / ignore

Description Output
[ stub / generated description later                         Copy ]

Suggestions / References
BOOM suggestion: Heavy Metal Door Impact
Similar examples: ...

Issues
unknown_ascii: kuang
```

### 4.1 Token Review 交互

第一版不做复杂拖拽。

必须支持的基础动作：

- unknown → keep raw
- unknown → ignore
- unknown → map to canonical
- save alias to personal dictionary
- 修改后刷新 output

### 4.2 `kuang` 的处理

`kuang` 是 ASCII，但可能是拼音。默认不要猜。

默认结果：

```text
kuang → unknown_ascii / needs_review
```

用户可以手动映射：

```text
kuang → Metal Impact
```

保存后进入 Personal Dictionary。

---

## 5. 本轮 Codex 执行计划

本轮名称：

```text
FXName Engine v0.3 Architecture Scaffold
```

本轮目标：尽可能搭完整框架，但不能牺牲 Normalize 稳定性。

### 5.1 必须完成

1. 确认当前在 `main`。
2. 确认 PR #1 的 Normalize 基线已进入 `main`，否则先停下报告。
3. 新增 `fxengine/` 目录和 dataclass。
4. 把现有 Normalize 逻辑封装出 `fxengine.normalizer` facade。
5. `engine.py` 可以继续作为兼容入口，但不要继续膨胀。
6. 新增 Personal Dictionary 初版。
7. 新增 Preferences 初版。
8. 新增 Example Retrieval stub。
9. 新增 Metadata Writer stub。
10. 新增简洁 UI 原型或重构现有 `app.py` 到简洁手测布局。
11. 新增测试，覆盖 Normalize、unknown、personal dictionary、preference、BOOM suggestion 不覆盖 final。

### 5.2 可以先 stub 的功能

允许只做接口和 UI 占位：

- Polish
- Suggest
- Metadata Description
- Example Retrieval

但 stub 必须返回结构化结果，不能让调用方崩溃。

### 5.3 禁止事项

禁止：

- 接 UCSRenamer
- 恢复 unknown NLLB fallback
- BOOM suggestion 覆盖 final output
- 把 Polish/Suggest 逻辑混进 Normalize 默认路径
- 让 UI 一轮变得复杂到难手测
- 没有测试就改现有核心行为

---

## 6. 多轮执行质量要求

Codex 不要只做一轮 patch。按下面的多轮自检执行。

### Round A — 基线确认

运行：

```powershell
git checkout main
git pull
git branch --show-current
git log --oneline -5
python -m pytest tests/ -q
```

如果当前 `main` 没有 PR #1 的 Normalize 基线，停止并报告。

### Round B — 架构 scaffold

新增 `fxengine/`，先让所有新模块有最小可用实现和测试。

验收：

```powershell
python -m pytest tests/ -q
```

### Round C — UI 手测雏形

调整 UI，让用户能看到：

- input
- FXName output
- token review
- description output placeholder
- suggestions / references placeholder
- issues
- preference preset

UI 必须能启动。

### Round D — 行为测试补齐

新增/扩展测试：

```text
金属 门 撞击 → Metal Door Impact
火箭 发射 爆炸 long tail 5m → Rocket Launch Explosion Long Tail 5m
door 推开 wood → Door Push Open Wood
kuang → unknown_ascii / needs_review
add alias kuang → Metal Impact 后 kuang → Metal Impact
allow_distance_in_fxname=True 保留 5m
allow_distance_in_fxname=False 不把 5m 放进 FXName
BOOM suggestion exists but final output unchanged
metadata writer stub returns needs_review/stub result
```

### Round E — 最终报告

最后必须汇报：

1. 当前分支
2. commit sha
3. pytest 结果
4. 新增文件列表
5. 修改文件列表
6. UI 启动方式
7. 手测步骤
8. 已实现功能
9. stub 功能
10. 未实现功能
11. 已知风险
12. git status

---

## 7. 推荐手测脚本

手测输入：

```text
金属 门 撞击
木门滑开
door 推开 wood
火箭 发射 爆炸 long tail 5m
kuang
木门夔魍滑开
木门 oh my god 滑开
metal door impact
```

重点看：

- 是否保留顺序
- 是否不调用 NLLB 乱补 unknown
- unknown 是否清楚显示
- token review 是否可读
- output 是否可复制
- preference 是否影响 5m
- BOOM suggestion 是否没有覆盖 final

---

## 8. 当前阶段定义

完成本轮后，项目应达到：

```text
FXName Normalize 可日常试用
fxengine 架构已独立
UI 可手测
Personal Dictionary 有最小闭环
Preferences 有最小闭环
Polish / Suggest / Metadata / Retrieval 有接口占位
```

这时再继续下一阶段：

```text
Canonical Token Database 扩充
Personal Dictionary 操作优化
Example Retrieval 真实现
Metadata Description 真实现
FXName Polish 真实现
FXName Suggest 真实现
```

仍然不要接 UCSRenamer。
