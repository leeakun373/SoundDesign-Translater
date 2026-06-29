# PyInstaller 打包规格：把测试前端 + 模型 + 词典 + sqlite 打成单应用。
# 用法： pyinstaller translator_gui.spec   （或运行 tools/build_gui.ps1）
# 注意：会很大（NLLB 模型本体几百 MB），首次启动解包较慢。

import os
from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(".")

datas = [
    (os.path.join(ROOT, "nllb_int8_model"), "nllb_int8_model"),
    (os.path.join(ROOT, "glossary", "boom_style_index.sqlite"), "glossary"),
    (os.path.join(ROOT, "glossary", "sources", "cc-cedict", "cedict_ts.u8"),
     os.path.join("glossary", "sources", "cc-cedict")),
    (os.path.join(ROOT, "translator", "data"), os.path.join("translator", "data")),
    (os.path.join(ROOT, "fxengine", "data", "canonical_tokens.csv"),
     os.path.join("fxengine", "data")),
]

hiddenimports = (
    collect_submodules("ctranslate2")
    + collect_submodules("transformers")
    + ["jieba", "rapidfuzz", "sentencepiece"]
)

a = Analysis(
    ["translator_gui.py"],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["torch", "tensorflow", "matplotlib", "scipy"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="SoundDesignTranslator",
    console=False,
    icon=None,
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    name="SoundDesignTranslator",
)
