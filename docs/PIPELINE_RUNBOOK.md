# 翻译管线运行手册（给新 AI）

> 目标：让你能**独立跑这套中文→FXName 翻译管线、并持续提升正确率**。
> 当前水平（held-out BOOM ONE 2500 条）：**token-F1 = 0.796，完全匹配 964/2500**。
> 你的工作不是大改架构，而是**喂数据 + 调几个旋钮 + 验收别让分数掉**。

---

## 0. 先读红线（来自 AGENTS.md，必须守）

- ❌ 不改 `fxengine/data/canonical_tokens.csv`（治理表，只读）
- ❌ 不 promote、不调外部 AI、不把 review 改成 keep
- ✅ 你能改的：`translator/data/fx_overrides*.csv`、`tools/mine_overrides_bilingual.py` 的阈值、`translator/data/fx_overrides.csv`（手工层）
- 每轮结束跑 `python -m pytest tests/ -q`，必须保持 **457 passed**

---

## 1. 管线心智模型（30 秒）

中文 → 分词 → 逐 token 翻译 → BOOM 风格吸附 → 组装成 FXName。
逐 token 翻译走**优先级覆盖**：

```
短语2gram(fx_overrides_phrase.csv) > 手工(fx_overrides.csv) > 双语挖掘(fx_overrides_bilingual.csv) > canonical(只读) > cedict自动 > CC-CEDICT > NLLB兜底
```

> 正确率主要由**双语挖掘层**决定——它从「精翻」中英对照里自动学 `撞击→Impact` 这种受控词汇。
> **短语层**解决多义词上下文：`开关 关闭→Switch Off`、`拉 关闭→Pull Off`（相邻两词命中时优先于逐词翻译）。

---

## 2. 怎么跑管线

```powershell
# 单条肉眼看（最快，带 token 轨迹）
python tools/quick_fxname_smoke.py "玻璃杯清脆碰撞" "远处沉闷的雷声"

# 独立测试前端（手动选模式：中→FXName / 中→英 / 英→中）
python translator_gui.py

# 在真实精翻数据上量化（留出集 = 没参与学词的数据，诚实）
python tools/mine_overrides_bilingual.py          # 80/20 留出，写 jingfan_holdout.csv
python tools/eval_jingfan.py --holdout translator/data/jingfan_holdout.csv --sample 2500
#   -> reports/jingfan_eval_*.md（含「高频缺失 token」「最差样例」）
```

精翻数据在 `docs/训练数据/` 及子目录 `精确翻译/`（三列：`完整原始名字,原FXName,中文翻译`）。
工具会**递归扫描并按文件名去重**，新增 CSV 直接被发现。

---

## 3. 怎么提升正确率（按性价比排序）

### 杠杆 A：喂更多精翻数据（最有效，零代码）
- 让便宜 AI 按 `docs/训练数据/精确翻译/_精翻规范.md` 翻更多 BOOM 库（优先 CK，跳过 DS）。
- 翻完丢进 `精确翻译/`，跑：
  ```powershell
  python tools/mine_overrides_bilingual.py --all   # 学进生产覆盖表
  ```
- 每多一个库，覆盖词汇变多，F1 应上升。**这是分数从 0.56→0.80 的主因。**

### 杠杆 B：调挖词器阈值（`tools/mine_overrides_bilingual.py` 顶部）
用 **Dice 关联度**对齐中英 token（降权 the/large 这种到处出现的词）。旋钮：

| 参数 | 含义 | 调大 | 调小 |
|---|---|---|---|
| `MIN_SUPPORT` | 中文词至少出现多少行才学 | 更准、更少 | 更全、更糙 |
| `MIN_BEST` | 最佳英文的共现行数下限 | 同上 | 同上 |
| `DICE_MIN` | 关联度下限 | 更准 | 更全 |
| `RATIO` | 最佳/次佳之比（要明显胜出） | 更准 | 更全 |

> 改完务必 A/B 验收（见 §4），别一味放宽导致引入错词。

### 杠杆 C：手工补系统性错词（`translator/data/fx_overrides.csv`，最高优先级）
看 eval 报告的「高频缺失 token」。若某词挖词器学不到或学错（如 `柔/金属` 偶尔漏），手动加一行：
```
raw,canonical,slot
金属,Metal,
柔,Soft,
```
手工层覆盖一切，立即生效。适合修「明显且高频」的个别错。

### 杠杆 D：分词 / 吸附（少碰）
- 某中文词被拆错 → 补 `translator/data/jieba_userdict.txt` 或 cedict。
- 输出风格不像 BOOM（单复数/拼写）→ `translator/boom_snap.py` 阈值。

---

## 4. 验收标准（每轮必做）

A/B 对比，确认改动**没让分数倒退**：

```powershell
python tools/mine_overrides_bilingual.py                 # 重新留出+学词
python tools/eval_jingfan.py --holdout translator/data/jingfan_holdout.csv --sample 2500   # 改动后
# 把 fx_overrides_bilingual.csv 暂时移走，再 eval 一次 = 基线
python tools/mine_overrides_bilingual.py --all           # 最后回到生产全量
python -m pytest tests/ -q                                # 必须 457 passed
```

- 当前基线：**held-out F1 = 0.796**。你的改动应 **≥ 0.796** 才算 OK。
- DS 创意名（专有名词如 `Mystisweep`）天然翻不准，别为它们牺牲整体分数。

---

## 5. 一轮工作的标准产出（汇报模板）

```
本轮做了：<加了哪些精翻库 / 调了哪个阈值 / 加了几条手工覆盖>
F1：改动前 0.xxx -> 改动后 0.xxx（held-out 2500）
pytest：457 passed
canonical 改动：无    promote：无    外部AI：无
```
