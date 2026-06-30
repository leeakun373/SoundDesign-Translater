# FXName 相关数据表总览

> 统计基准：2026-06-30 本仓库本地实测。  
> 轨道 A（`translator/`）= 活跃 FXName 中→英；轨道 B（`fxengine/`）= Legacy canonical 治理。

---

## 一句话：FXName 管线吃哪些表

```
输入
 → jieba 分词（jieba_userdict.txt 缓存）
 → 相邻两中文词：fx_overrides_phrase.csv
 → 单 token：四表合并 lookup（手工 > 双语 > canonical > 自动）
 → 未命中：CC-CEDICT
 → 仍 unknown：略去，不翻
 → boom_snap：boom_style_index.sqlite + zh_en_alignment.csv 闸门
 → fx_slots 组装
```

**入口**：`translator/api.py` → `to_fxname()` → `fxname_mode.normalize()`

---

## 一、FXName 运行时真正在用（8 个数据源）


| #   | 文件                                           | 行数/规模                                   | 干什么                                   | 有没有用                    |
| --- | -------------------------------------------- | --------------------------------------- | ------------------------------------- | ----------------------- |
| 1   | `translator/data/fx_overrides.csv`           | **492**                                 | 手工策展，**最高优先级**；修 cedict/自动误判          | ✅ **核心维护表**             |
| 2   | `translator/data/fx_overrides_bilingual.csv` | **2,922**                               | 精翻对照挖的双语观测真值                          | ✅ 运行时（压 canonical/auto） |
| 3   | `fxengine/data/canonical_tokens.csv`         | **588**（zh+keep 子集）/ **718** 全表         | 轨道 B 治理过的 FX 策展译法；轨道 A **只读** keep 子集 | ✅ 运行时（只读子集）             |
| 4   | `translator/data/fx_overrides_auto.csv`      | **48,197**                              | BOOM 词频 + cedict 自动择优                 | ✅ 运行时（**最低**优先级，噪声多）    |
| 5   | `translator/data/fx_overrides_phrase.csv`    | **1,884**                               | 相邻 2 词短语（如「开关 关闭」）                    | ✅ 运行时（**先于**单 token）    |
| 6   | `glossary/sources/cc-cedict/cedict_ts.u8`    | **115,118** 简体词头                        | override 全未命中时的兜底译法                   | ✅ 运行时                   |
| 7   | `glossary/boom_style_index.sqlite`           | **16,005** tokens / **363,408** phrases | BOOM 全库词频吸附、形变体替换                     | ✅ 运行时                   |
| 8   | `translator/data/zh_en_alignment.csv`        | **168,452** (zh,en) 对                   | boom_snap 同义替换的「符合中文输入」证据闸门           | ✅ 运行时                   |


**合并后实际单 token 查表键数：50,267**（四表 raw 并集更大，靠优先级去重）。

### 四表合并顺序

见 `translator/overrides.py`：

```python
# 优先级：手工 > 双语挖掘 > canonical(keep) > cedict自动
table = _read_override_csv(FX_OVERRIDES_AUTO_PATH)       # 最低
table.update(_load_canonical())                          # canonical(keep) 覆盖自动
table.update(_read_override_csv(FX_OVERRIDES_BILINGUAL_PATH))
table.update(_read_override_csv(FX_OVERRIDES_PATH))       # 手工最高
```

### 单 token 翻译优先级（无 NLLB）

见 `translator/fxname_mode.py` → `_translate_zh_token()`：

1. `overrides.lookup(tok)` → source=`override`
2. `cedict.lookup(tok)` → source=`cedict`
3. 否则 → source=`unknown`（从最终名略去，**不调用 AI/NLLB**）

### 路径常量


| 常量                            | 路径                                           | 定义位置                      |
| ----------------------------- | -------------------------------------------- | ------------------------- |
| `FX_OVERRIDES_PATH`           | `translator/data/fx_overrides.csv`           | `translator/overrides.py` |
| `FX_OVERRIDES_AUTO_PATH`      | `translator/data/fx_overrides_auto.csv`      | `translator/overrides.py` |
| `FX_OVERRIDES_BILINGUAL_PATH` | `translator/data/fx_overrides_bilingual.csv` | `translator/overrides.py` |
| `FX_OVERRIDES_PHRASE_PATH`    | `translator/data/fx_overrides_phrase.csv`    | `translator/overrides.py` |
| `CANONICAL_PATH`              | `fxengine/data/canonical_tokens.csv`         | `translator/overrides.py` |
| `CEDICT_PATH`                 | `glossary/sources/cc-cedict/cedict_ts.u8`    | `translator/cedict.py`    |
| `BOOM_INDEX_PATH`             | `glossary/boom_style_index.sqlite`           | `translator/boom_snap.py` |
| `ALIGN_PATH`                  | `translator/data/zh_en_alignment.csv`        | `translator/align.py`     |
| `USERDICT_PATH`               | `translator/data/jieba_userdict.txt`         | `translator/segment.py`   |


---

## 二、FXName 生成物/缓存（不直接查，缺了会重建）


| 文件                                   | 行数          | 干什么                                  | FXName 用不用 |
| ------------------------------------ | ----------- | ------------------------------------ | ---------- |
| `translator/data/jieba_userdict.txt` | **105,990** | cedict 词头 ∪ override 键 → jieba 自定义词典 | ✅ 分词用      |


生成逻辑：`translator/segment.py` → `build_userdict()`  
来源 = `cedict.headwords(min_len=2)` + `overrides.keys()`（长度≥2 的中文键）

`.gitignore`（`translator/data/.gitignore`）标为本地生成、不入库；**四张 override 表除外**（带 `!` 强制跟踪）。

---

## 三、FXName 构建原料（只给 mine/align 脚本用，不进 translate 直查）


| 文件                                                          | 行数        | 谁生成          | 喂给谁                                           |
| ----------------------------------------------------------- | --------- | ------------ | --------------------------------------------- |
| `docs/boom_mining/boom_one_mining_v0_1_b001_candidates.csv` | **1,530** | BOOM 语料挖掘    | `translator/align.py` → `zh_en_alignment.csv` |
| `docs/boom_mining/boom_one_mining_v0_1_b001_samples.csv`    | —         | 挖掘样本         | 文档/审计                                         |
| `docs/boom_mining/boom_one_mining_v0_1_b001_rejected.csv`   | —         | 被拒候选         | 文档/审计                                         |
| `docs/boom_mining/boom_one_mining_v0_1_b001_promoted.csv`   | —         | 已 promote 记录 | 轨道 B 历史                                       |


### 对齐表三源合并（`translator/align.py`）


| 来源                         | support 权重 |
| -------------------------- | ---------- |
| canonical_tokens.csv keep  | 3          |
| boom_one mining candidates | 2          |
| CC-CEDICT 全量词头             | 1          |


### 构建脚本 → 输出


| 脚本                                    | 输出                             |
| ------------------------------------- | ------------------------------ |
| `tools/mine_overrides.py`             | → `fx_overrides_auto.csv`      |
| `tools/mine_overrides_bilingual.py`   | → `fx_overrides_bilingual.csv` |
| `translator/align.build()` / 相关工具     | → `zh_en_alignment.csv`        |
| `translator/segment.build_userdict()` | → `jieba_userdict.txt`         |


---

## 四、老 engine 整句/文件名（模式 2/3/4，不是 FXName）


| 文件                                      | 行数                                   | 干什么           | FXName 用不用               |
| --------------------------------------- | ------------------------------------ | ------------- | ------------------------ |
| `glossary/audio_glossary.sqlite`        | **10,998** glossary + **753** catids | 整句/文件名术语替换    | ❌                        |
| `glossary/user_overrides.csv`           | **110**                              | 术语库最高优先级人工覆盖  | ❌ 建 sqlite 用             |
| `glossary/sources/MyKeyWordV1.csv`      | **374**                              | 自整理音效关键词底库    | ❌ 建 sqlite 用             |
| `glossary/sources/ucs_catid_list.csv`   | —                                    | UCS CatID     | ❌ 建 sqlite 用             |
| `glossary/sources/ucs_categorylist.csv` | —                                    | UCS 官方分类（可选）  | ❌ 建 sqlite 用             |
| `glossary/zh_oral_aliases.csv`          | **27**                               | 中→英口语 compose | ❌                        |
| `glossary/packs/zh_fx_patterns.csv`     | **94**                               | 短语模式 compose  | ❌ 老 fxengine normalize 用 |


- `engine.py` 走 `GlossaryMatcher(audio_glossary.sqlite)`。
- `translator/api.py` 的 `to_fxname()` **绕开**这条路径。
- `glossary/fx_slots.py` 里 `TOKEN_SLOT_OVERRIDES` 是**代码内硬编码**，不是 CSV；FXName 组装 slot 时会用。

重建术语库：`python glossary/build_glossary.py`

---

## 五、轨道 B canonical 治理（Legacy，agent 默认禁止改）


| 文件                                             | 行数      | 干什么                                | FXName 关系                 |
| ---------------------------------------------- | ------- | ---------------------------------- | ------------------------- |
| `fxengine/data/canonical_tokens.csv`           | **718** | 受治理主表（en+zh，含 review 状态）           | 轨道 A **只读** zh+keep→588 条 |
| `fxengine/data/canonical_token_candidates.csv` | **0**   | promote 候选池                        | ❌ 当前空                     |
| `fxengine/data/canonical_token_conflicts.csv`  | **0**   | 冲突审计                               | ❌ 当前空                     |
| `exports/ai_alias_prompt_pack/*.csv`           | 若干      | AI alias 审查 intake/decision/review | ❌ 治理工作流                   |
| `exports/alias_workbench/*.csv`                | 若干      | 中文 alias 工作台                       | ❌ 治理工作流                   |


详见 `AGENTS.md`、`docs/AI_ALIAS_WORKFLOW.md`。

---

## 六、测试 / 评估 / 报告（全都不进运行时）


| 文件                                         | 规模      | 用途                                   |
| ------------------------------------------ | ------- | ------------------------------------ |
| `docs/模拟测试报告/模拟测试结果.csv`                   | **150** | 基准探针（中→英 FXName）                     |
| `docs/模拟测试报告/simulated_test_500_v0_2.csv`  | **500** | 更大基准集                                |
| `tests/zh_fxname_governance_cases_50.csv`  | **50**  | pytest 治理回归                          |
| `tests/zh_fxname_governance_cases_150.csv` | **150** | pytest 治理回归                          |
| `tests/zh_fxname_probe_regression.csv`     | **1482** | R13–R45 探针固化回归（translator 轨道 A）   |
| `tests/fxname_quality_cases.csv`           | —       | 质量 harness                           |
| `tests/fixtures/fxname_manual_cases.csv`   | —       | fxengine 手工用例                        |
| `tests/smoke_real_cases.csv`               | —       | 冒烟                                   |
| `translator/data/boom_zh_testcases.csv`    | **30**  | `tools/eval_boom_full.py`（gitignore） |
| `tests/results/*.csv` / `*.json`           | —       | 跑测输出                                 |
| `reports/jingfan_eval_*.md`                | —       | 评估报告 markdown                        |


相关工具：

- `tools/run_sim_test_zh2en.py` — 150 条基准 + token 来源统计
- `tools/probe_fxname.py` — 按行探针
- `tools/build_probe_regression_csv.py` — 将 `tools/_probe_r*.txt` 固化为 `tests/zh_fxname_probe_regression.csv`

---

## 七、维护 ROI 排序（你该盯哪几张）


| 优先级   | 表                                          | 原因                               |
| ----- | ------------------------------------------ | -------------------------------- |
| ⭐⭐⭐   | `fx_overrides.csv`（492）                    | 手工、最高优先级、改一行立刻生效                 |
| ⭐⭐    | `fx_overrides_phrase.csv`（1884）            | 消歧义（多义词靠上下文）                     |
| ⭐     | `fx_overrides_bilingual.csv`（2922）         | 观测真值，一般只增不改                      |
| 重建别手改 | `fx_overrides_auto.csv`（48197）             | 体量大、有噪声 → `mine_overrides.py` 重建 |
| 只读    | `canonical_tokens.csv` keep（588）           | 轨道 B 产物，轨道 A 只读                  |
| 别手改   | `zh_en_alignment.csv`（168452）              | `align.build()` 生成               |
| 别手改   | `jieba_userdict.txt`（105990）               | `build_userdict()` 生成            |
| 基础设施  | `cedict_ts.u8` + `boom_style_index.sqlite` | 换源/重建成本高，平时不动                    |


**设计共识**：FXName 宁可 unknown 也不乱翻；维护 ROI 最高的是手工表 + 少量短语表。自动层体量大、有噪声，应用 mine 重建 + 提高阈值，而非逐行改 auto。

---

## 八、重叠说明（避免「表多 = 覆盖大」误解）


| 概念                              | 数量         | 说明                            |
| ------------------------------- | ---------- | ----------------------------- |
| 四 override + canonical 子集 raw 行 | ~5.2 万     | 同词多表重复                        |
| **合并单 token lookup 键**          | **50,267** | 手工赢重复键                        |
| phrase 表                        | 1,884      | **独立通道**，不算进 50,267           |
| cedict 词头                       | 115,118    | 兜底池，override 未命中才查            |
| alignment (zh,en) 对             | 168,452    | **不是翻译表**，只给 boom_snap 同义替换闸门 |


手工 ∩ 自动重叠约 **108** 键（其中约 **81** 译法不同，**手工优先**）。

---

## 九、轨道 A vs 轨道 B


|           | 轨道 A `translator/`                                 | 轨道 B `fxengine/`                  |
| --------- | -------------------------------------------------- | --------------------------------- |
| 用途        | 活跃：中→英 FXName                                      | Legacy：canonical 治理、alias promote |
| canonical | **只读** `canonical_tokens.csv`（zh+keep 并入 override） | **禁止 agent 修改**                   |
| NLLB      | FXName **已禁用**；整句模式仍可用                             | 不涉及                               |


---

## 相关文档

- [翻译系统_大白话说明.md](翻译系统_大白话说明.md)
- [TRANSLATOR_ARCHITECTURE.md](TRANSLATOR_ARCHITECTURE.md)
- [TRANSLATOR_METHODOLOGY.md](TRANSLATOR_METHODOLOGY.md)
- [cc_cedict/cc_cedict_candidate_layer_v0_1.md](cc_cedict/cc_cedict_candidate_layer_v0_1.md)
- [glossary/README.md](../glossary/README.md)
- [fxengine/data/README.md](../fxengine/data/README.md)

