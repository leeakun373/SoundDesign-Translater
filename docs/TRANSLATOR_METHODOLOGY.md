# Translator 方法论：怎么测、怎么调、何时做什么、能不能换模型

> 面向：维护者 / 便宜 LLM agent
> 目标：让这套引擎**长期低维护**地覆盖尽可能多的命名情况

---

## 0. 一句话心智模型

> **NLLB/词典负责「翻得出来」，BOOM 全库负责「翻得像」，自动挖掘负责「不用人天天调」。**

模式1（中文→FXName）分层，**修问题时按层定位**：

| 层 | 文件 | 职责 | 出问题时改这里 |
|----|------|------|----------------|
| 分词 | `translator/segment.py` + `data/jieba_userdict.txt` | 整词不拆字 | 某词被拆 → 补 userdict / cedict |
| 手工覆盖 | `translator/data/fx_overrides.csv` | 高频/易错词的人工定译 | 自动层选错义（厚/快/轻）→ 加一行 |
| canonical | `fxengine/data/canonical_tokens.csv`（只读） | 受治理 FX 译法 | 不在此改（治理表） |
| 自动覆盖 | `translator/data/fx_overrides_auto.csv` | 按 BOOM 词频自动定译 | 重新跑 `mine_overrides.py` |
| cedict | `translator/cedict.py` | 通用兜底 | 清洗规则问题改这里 |
| NLLB | `translator/nllb.py` | 长尾兜底 | 换模型只改这一个文件 |
| BOOM 吸附 | `translator/boom_snap.py` | 把结果吸附成 BOOM 写法 | 吸附过激/不足 → 调阈值 |
| 组装 | `glossary/fx_slots.py` | slot 排序/Title Case | 语序问题改这里 |

优先级：手工 > canonical > 自动 > cedict > NLLB。

---

## 1. 怎么测（三个工具，由快到全）

```powershell
# A. 单条/几条，开发期肉眼看（秒级）
python tools/quick_fxname_smoke.py "喷火器" "金属门重重关上"

# B. 1000 对中英 FXName 黄金集，量化 token-F1（约 20-50s）
python tools/eval_translator.py
#  -> reports/translator_eval_*.md（含最差样例）

# C. 全 BOOM 库覆盖测（长跑，便宜模型可跑很久）
python tools/gen_zh_testcases.py --limit 80000      # 先造中文测试输入
python tools/eval_boom_full.py                      # 再跑覆盖+最差token挖掘
```

**指标口径**：token 级集合 Precision/Recall/F1 + 集合完全匹配率。
当前基线：新引擎 **F1≈0.71 / exact 144/1000**，旧确定性流水线 F1=0.108 / exact 0。

---

## 2. 怎么调试（看 token 决策）

`quick_fxname_smoke.py` 对每个 token 打印：`输入 -> 译文 => 吸附后 [来源+决策] 词频`。

决策码含义：
- `override/canonical/cedict/nllb` = 译文来源
- `kept_common` = BOOM 已常见，保留
- `snapped_form` = 形变体归一（flame thrower→Flamethrower）
- `snapped_boom_variant` = 同义 BOOM 写法替换（有对齐证据）
- `kept_model` = BOOM 不常见且无安全替换，保留
- `dropped_stop` = 中文虚词丢弃

**判断该改哪层**：
- 译文本身就错（义项错）→ 看来源；cedict/auto 错就加 `fx_overrides.csv` 一行
- 译对了但不像 BOOM → 调 `boom_snap.py` 阈值（`PHRASE_COMMON/TOKEN_COMMON/VARIANT_MIN`）
- 词被拆碎 → 补 `jieba_userdict`
- 虚词混进结果 → 加 `fxname_mode.ZH_STOP` / `EN_DROP`

---

## 3. 何时做什么（维护工作流）

| 触发 | 动作 |
|------|------|
| 日常某条不像 | smoke 定位 → 改对应层一行 → eval 确认不退化 |
| 词典/对齐源更新 | `python -m translator.segment --build`；`python -m translator.align`；`python tools/mine_overrides.py` |
| 想扩大覆盖 | 跑全 BOOM 长跑（见第 5 节），用挖掘出的最差 token 批量补 `fx_overrides` |
| 阈值想收紧/放宽 | 改 `boom_snap.py` 常量，跑 eval 看 F1 变化 |

**关键：不要手工堆词表追覆盖。** 覆盖靠 `mine_overrides.py`（数据驱动、可重生成），
人只维护一张小的「例外表」`fx_overrides.csv`（自动选错时才加）。

---

## 4. 能不能换模型 / 便宜模型能不能接手

**能，而且很彻底。** 关键是：贵模型**不在 runtime 里**。

- **runtime（模式1 FXName）几乎不依赖 NLLB**：绝大多数 token 命中 override/canonical/cedict，
  NLLB 只兜长尾。换掉 NLLB 只改 `translator/nllb.py`（两个函数 `zh2en/en2zh`）。
- **贵的 API（Opus 等）只用于「离线造测试数据」与「可选的批量建议」**，不是翻译引擎的一部分。
  造数据用哪个模型都行，甚至可用**免费本地 NLLB**（见下）。所以便宜模型完全能接手我的工作：
  - 它的活 = 跑 `gen_zh_testcases.py` 造中文、跑 `eval_boom_full.py` 看分数、把最差 token 整理进 `fx_overrides.csv`。
  - 这些都是确定性脚本 + 词表编辑，不需要强模型推理。

**结论**：贵模型可省。引擎质量主要由 BOOM 数据 + 词典决定，不由某个 LLM 决定。

---

## 5. 用便宜模型「跑很久、覆盖全 BOOM」的配方（你的核心诉求）

我们没有 80k 条真实中文，但有 80k 条真实**英文** FXName（目标）。做法：**回译造测试**。

```powershell
# 第一步：把 BOOM 英文 FXName 回译成中文，作为测试输入（可跑很久、可断点续跑）
#   默认用本地 NLLB（零成本、离线）；也可接你的便宜 API（更自然的中文）
python tools/gen_zh_testcases.py --limit 80000
python tools/gen_zh_testcases.py --provider openai --limit 80000   # 用便宜 API

# 第二步：跑全量覆盖测，对比真实英文，产出最差 token 排行
python tools/eval_boom_full.py
#   -> reports/boom_full_eval_*.md（F1 + 高频「翻不出来/翻不像」的 token）

# 第三步：把最差且高频的 token 批量补进 fx_overrides（人或便宜模型都能做）
#   然后重跑第二步看分数上升
```

为什么有效：回译中文有噪声，但**在 8 万条规模上系统性暴露**「哪些 BOOM 英文词我们的管线复现不了」，
这正是要补的覆盖缺口。便宜 API 量大，正好喂第一步。

> 注意：回译评测的绝对分会被回译噪声拉低，**看相对提升和最差 token 排行**，不要只看绝对 F1。

---

## 6. 资源重建命令速查

```powershell
python -m translator.segment --build      # jieba_userdict.txt
python -m translator.align                # zh_en_alignment.csv
python tools/mine_overrides.py            # fx_overrides_auto.csv（数据驱动覆盖）
python -m pytest tests/test_translator.py -q
```
