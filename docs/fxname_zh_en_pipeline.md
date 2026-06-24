# FXName 中英命名流程

## 默认目标

当前中 -> 英路径默认服务于 FXName 命名，主要用于录音文件、BB、DS、Soundminer 等音效库命名场景。

目标输出不是自然句，而是短、清晰、可检索的英文关键词串，例如：

- `Wood Door Slide`
- `Pour Water Into Cup`
- `Tire Rub`
- `Saw Wood`

## 当前流程

1. 中文 compose 先做最长匹配，把明确的中文音效片段转成英文 FX 词。
2. glossary 提供已有术语和口语别名。
3. NLLB fallback 只补 compose 未覆盖的 unknown 中文片段。
4. slot-aware assembler 按音效命名槽位组合词序。
5. Boom index 作为英文风格参考。
6. validator 检查输出是否缺核心词、是否像自然句、是否信息量过低。

## 模块职责

`glossary/packs/zh_fx_patterns.csv`

少量强约束 pattern。只放真实 smoke 或明确回归里反复失败的短词、复合词和高价值短语，优先级高于普通 glossary 同义词。

`NLLB`

只补 unknown 中文，不负责整块翻译短中文 FXName。短词如果已知，应优先进入 pattern 或 glossary 分段。

`glossary/fx_slots.py`

决定基础词序。它把词拆到 material、object、action、detail 等槽位，再按稳定规则组装，避免出现 `Drop Box` 这类倒置结果。

`glossary/boom_style.py`

只做英文风格参考。它可以帮助贴近 Boom/BB/DS 命名习惯，但不应推翻 slot-aware assembler 的基础词序。

`glossary/fx_name.py`

质量检查。负责发现 missing token、自然句、低信息量、禁用词等问题。它不应把所有包含某个汉字的中文都当成对应物体，例如不能因为“油门”包含“门”就要求 `Door`。

## 如何新增少量失败词

1. 先看真实 smoke 输出和 validator issue，确认是高频、明确、可复现的失败。
2. 如果是短中文复合词被 glossary 同义词抢走，优先在 `glossary/packs/zh_fx_patterns.csv` 加一条强约束 pattern。
3. 如果只是 validator 误报，优先修 `glossary/fx_name.py` 的检查规则，不补无关词。
4. 每次只补少量真实失败词，避免把词表扩成泛化规则库。
5. 补完必须加 targeted regression，通常放在 `tests/test_fx_name_matrix.py`。

## 测试命令

```bash
python tests/test_boom_style_index.py
python tests/test_fx_name_matrix.py
python tests/run_all_tests.py
python tools/run_smoke_real_cases.py
```

阶段收尾时至少跑前三个；改真实 smoke 覆盖范围时再跑 `tools/run_smoke_real_cases.py`。

## 当前限制

武器、生物、复杂环境长描述仍需真实样本继续观察。当前策略优先保证短中文 FXName 和真实高频失败词稳定，不用大规模规则覆盖所有长描述。
