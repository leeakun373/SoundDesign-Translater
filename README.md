# SoundDesign Translater

本地离线音效翻译：中文 → BOOM 风格英文音效名，以及中英互译/整句翻译。全程离线。

---

## ⭐ 当前方向（Current Direction）— 先看这里

**现在的主翻译引擎是 `translator/`（混合引擎）**：jieba 分词 + 词典/CC-CEDICT + 本地 NLLB 兜底 + BOOM 全库风格吸附。
旧的纯词表确定性流水线（`fxengine` normalize）与老 GUI **保留不删，仅作 legacy/参考**。

| 想了解什么 | 看这个 |
|------------|--------|
| **大白话：用了哪些文件、怎么翻的** | [docs/翻译系统_大白话说明.md](docs/翻译系统_大白话说明.md) |
| 技术架构（分层、吸附逻辑） | [docs/TRANSLATOR_ARCHITECTURE.md](docs/TRANSLATOR_ARCHITECTURE.md) |
| 方法论（怎么测/调/维护/换模型） | [docs/TRANSLATOR_METHODOLOGY.md](docs/TRANSLATOR_METHODOLOGY.md) |
| 给其他 AI 的导航 | [AGENTS.md](AGENTS.md) 顶部 |

四种能力（统一入口 `translator/api.py`）：中文→FXName 关键词英文、英→中、中→英整句、英文长句→中。

常用命令：

```powershell
python tools/quick_fxname_smoke.py "喷火器" "金属门重重关上"   # 看单条翻译+每词决策
python tools/eval_translator.py                              # 1000 对黄金集打分(F1≈0.71)
python tools/mine_overrides.py                               # 重建数据驱动的自动译法表
```

当前 GUI（`python app.py`）的「FXName / 音效命名」任务已接入新引擎。

---

## （Legacy / 保留）老术语库系统核心路径

| 用途 | 路径 |
|------|------|
| **你维护的主表** | `glossary/user_overrides.csv` |
| **中文口语别名** | `glossary/zh_oral_aliases.csv` |
| **底库 CSV（已随仓库）** | `glossary/sources/*.csv` |
| **生成术语库** | `build_glossary.bat` → `glossary/audio_glossary.sqlite` |
| **翻译模型** | `nllb_int8_model/`（见下方下载） |
| **配置说明** | [docs/模型与配置.md](docs/模型与配置.md) |
| **测试报告** | `tests/results/latest_report.md` |

---

## 首次安装

```powershell
git clone https://github.com/leeakun373/SoundDesign-Translater.git
cd SoundDesign-Translater

pip install -r requirements.txt

# 下载模型（~600MB，GitHub Release）
powershell -ExecutionPolicy Bypass -File scripts/download_assets.ps1

# 或已有模型目录时，仅重建术语库
build_glossary.bat

# 双击启动 FXName Review UI（Normalize 不需要加载 NLLB 模型）
启动翻译工具.bat

# 输入后按 Enter 直接生成；Shift+Enter 可在输入框换行

# 如需旧版完整翻译 GUI / General NLLB
python app.py
```

---

## 术语库怎么生成

```
glossary/user_overrides.csv     ← 你维护（最高优先级）
        +
glossary/sources/MyKeyWordV1.csv
        +
glossary/sources/ucs_catid_list.csv
        +
glossary/sources/ucs_categorylist.csv
        ↓
glossary/build_glossary.py
        ↓
glossary/audio_glossary.sqlite   ← 运行时查表（可随 Release 下载或本地 build）
```

环境变量可覆盖底库 CSV 路径，见 [docs/模型与配置.md](docs/模型与配置.md)。

---

## 日常维护

1. 改 `glossary/user_overrides.csv` 或 `glossary/zh_oral_aliases.csv`
2. `build_glossary.bat`
3. 重启 GUI / HTTP 服务

---

## 测试

```powershell
python tests/run_all_tests.py
# 或 run_tests.bat
```

---

## 可选工具（需自备商业库）

```powershell
set UCS_COMMERCIAL_DB=path\to\ucs_assets.db
python tools/find_uncovered_terms.py --db %UCS_COMMERCIAL_DB%
```

---

## 文档

### AI Alias 治理（给 Cursor / 本地 AI）

- [AGENTS.md](AGENTS.md) — agent 入口
- [docs/PROJECT_INVARIANTS.md](docs/PROJECT_INVARIANTS.md) — 项目不变量
- [docs/AI_ALIAS_WORKFLOW.md](docs/AI_ALIAS_WORKFLOW.md) — Evidence → Decision 全流程
- [docs/AI_ALIAS_REVIEW_RULES.md](docs/AI_ALIAS_REVIEW_RULES.md) — 审查与 batch 规则
- [docs/LOCAL_AI_AGENT_PLAYBOOK.md](docs/LOCAL_AI_AGENT_PLAYBOOK.md) — 每轮操作清单
- [docs/BATCH_PROMOTION_PLAN.md](docs/BATCH_PROMOTION_PLAN.md) — 未来 promote 路线（未启用）

### 其它

- [docs/开发历史.md](docs/开发历史.md) — **开发上下文压缩版（给后续会话用）**
- [docs/模型与配置.md](docs/模型与配置.md)
- [docs/CANONICAL_TOKEN_GOVERNANCE.md](docs/CANONICAL_TOKEN_GOVERNANCE.md)
- [docs/CANONICAL_TOKEN_WORKFLOW.md](docs/CANONICAL_TOKEN_WORKFLOW.md)
- [glossary/README.md](glossary/README.md)
- [docs/补词批量验收指南.md](docs/补词批量验收指南.md)
