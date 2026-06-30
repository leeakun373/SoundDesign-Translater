# SoundDesign FXName 安装包版路径说明

本文档用于提前了解“打包/安装会产生哪些文件，以及它们会出现在哪里”。

当前方案是 **FXName-only 安装包**：

- 只包含中文/中英混合 -> BOOM 风格 FXName。
- 不包含 `nllb_int8_model/`。
- 不加载 `engine.py` / NLLB 整句翻译。
- 默认保留 BOOM 风格吸附，因此会随安装包带上 `boom_style_index.sqlite`。

---

## 1. 源码里新增的文件

这些文件会进入 Git 仓库：

| 路径 | 用途 |
|---|---|
| `fxname_app.py` | FXName-only tkinter 桌面入口；不 import NLLB。 |
| `tools/build_fxname_release.py` | 调 PyInstaller 生成 release 文件夹。 |
| `build/SoundDesignFXName.iss` | Inno Setup 安装器脚本。 |
| `requirements-fxname.txt` | 只打 FXName 安装包需要的最小依赖。 |
| `FXNAME_INSTALLER_PATHS.md` | 本文档。 |

---

## 2. 构建前准备

建议使用独立虚拟环境：

```powershell
python -m venv .venv-fxname
.\.venv-fxname\Scripts\Activate.ps1
pip install -r requirements-fxname.txt
```

如果要生成 `.exe` 安装器，还需要安装 **Inno Setup 6**，并确保 `ISCC.exe` 在 PATH 中。

---

## 3. 构建 release 文件夹会产生什么

命令：

```powershell
python tools/build_fxname_release.py
```

会生成：

```text
dist/
  SoundDesignFXName/
    SoundDesignFXName.exe
    _internal/
      translator/
        data/
          fx_overrides.csv
          fx_overrides_auto.csv
          fx_overrides_bilingual.csv
          fx_overrides_phrase.csv
          zh_en_alignment.csv
          jieba_userdict.txt
      fxengine/
        data/
          canonical_tokens.csv
      glossary/
        boom_style_index.sqlite
        sources/
          cc-cedict/
            cedict_ts.u8
      ...Python 运行时与依赖库...
```

同时会生成 PyInstaller 中间文件：

```text
build/
  pyinstaller_fxname/
  SoundDesignFXName.spec
```

这些是构建产物，可删除后重建。

### release 文件夹体积预估

| 部分 | 体积 |
|---|---:|
| `glossary/boom_style_index.sqlite` | 约 419 MB |
| 其它 FXName 数据 | 约 16 MB |
| Python 运行时 + jieba + rapidfuzz | 约 70-100 MB |
| **合计** | **约 500-550 MB** |

---

## 4. 生成安装器会产生什么

命令：

```powershell
ISCC build\SoundDesignFXName.iss
```

会生成：

```text
release/
  SoundDesignFXName_Setup_0.1.0.exe
```

安装器压缩后预计约 **200-300 MB**，实际大小以本机打包结果为准。

---

## 5. 用户安装后文件会去哪里

默认安装目录：

```text
C:\Program Files\SoundDesign FXName\
```

安装后大致结构：

```text
C:\Program Files\SoundDesign FXName\
  SoundDesignFXName.exe
  FXNAME_INSTALLER_PATHS.md
  unins000.exe
  unins000.dat
  _internal\
    translator\data\...
    fxengine\data\...
    glossary\...
    ...Python 运行时与依赖...
```

如果用户安装时修改了路径，则 `{app}` 会变成用户选择的目录。

### 快捷方式

安装器会创建：

```text
开始菜单\SoundDesign FXName\SoundDesign FXName.lnk
```

如果用户勾选桌面快捷方式，还会创建：

```text
Desktop\SoundDesign FXName.lnk
```

### 卸载信息

Inno Setup 会在 Windows 注册表写入卸载信息，用于“设置 -> 应用”里卸载。

---

## 6. 会不会写用户目录

当前 `fxname_app.py` 本身不主动写用户配置。

默认打包会带上 `translator/data/jieba_userdict.txt`，正常运行不需要重建 jieba 词典，因此不应该写入安装目录。

如果将来不打包 `jieba_userdict.txt`，程序会尝试生成它；安装在 `Program Files` 时可能因权限不足失败。所以安装包版建议始终带上该文件。

---

## 7. 不包含哪些东西

默认 FXName 安装包 **不包含**：

| 路径/组件 | 原因 |
|---|---|
| `nllb_int8_model/` | 约 617 MB，FXName 当前不需要。 |
| `ctranslate2` / `transformers` / `sentencepiece` | 仅整句 NLLB 翻译需要。 |
| `glossary/audio_glossary.sqlite` | 老 engine/整句术语模式用，FXName-only 不需要。 |
| `tests/` / `reports/` / `docs/模拟测试报告/` | 测试与报告，不属于运行时。 |

---

## 8. 如果要完整整句翻译版

完整整句翻译版需要额外设计一个可选组件：

```text
models/
  nllb_int8_model/
```

并额外安装/打包：

- `ctranslate2`
- `transformers`
- `sentencepiece`
- `glossary/audio_glossary.sqlite`

预计安装后总占用约 **1.3-1.5 GB**。

当前安装包脚本没有启用这个可选组件。

---

## 9. 推荐发布流程

```powershell
python -m pytest tests/test_zh_fxname_probe_regression.py -q
python tools/build_fxname_release.py
ISCC build\SoundDesignFXName.iss
```

产物：

```text
release/SoundDesignFXName_Setup_0.1.0.exe
```

交付给用户这个安装器即可。
