# SoundDesign Translater

本地离线音效翻译：NLLB + UCS/音效术语库。英→中（库文件名/描述）、中→英（中文写 FX 关键词）。

---

## 核心路径

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

# 启动 GUI
启动翻译工具.bat
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

- [docs/开发历史.md](docs/开发历史.md) — **开发上下文压缩版（给后续会话用）**
- [docs/模型与配置.md](docs/模型与配置.md)
- [glossary/README.md](glossary/README.md)
- [docs/补词批量验收指南.md](docs/补词批量验收指南.md)
