"""Build the FXName-only Windows release folder with PyInstaller.

This script creates ``dist/SoundDesignFXName``. It deliberately does not bundle
``nllb_int8_model`` or the NLLB dependencies used by the old general translator.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist" / "SoundDesignFXName"
BUILD_DIR = ROOT / "build" / "pyinstaller_fxname"
SPEC_DIR = ROOT / "build"
SPEC_PATH = SPEC_DIR / "SoundDesignFXName.spec"

from translator import paths as tpaths

DATA_FILES = (
    (tpaths.FX_OVERRIDES_PATH, "translator_assets/fxname"),
    (tpaths.FX_OVERRIDES_AUTO_PATH, "translator_assets/fxname"),
    (tpaths.FX_OVERRIDES_BILINGUAL_PATH, "translator_assets/fxname"),
    (tpaths.FX_OVERRIDES_PHRASE_PATH, "translator_assets/fxname"),
    (tpaths.ALIGN_PATH, "translator_assets/fxname"),
    (tpaths.USERDICT_PATH, "translator_assets/generated"),
    (tpaths.CANONICAL_PATH, "fxengine/data"),
    (tpaths.BOOM_INDEX_PATH, "translator_assets/indexes"),
    (tpaths.CEDICT_PATH, "translator_assets/dictionaries"),
)


def _add_data_args() -> list[str]:
    sep = os.pathsep
    args: list[str] = []
    for src, dest in DATA_FILES:
        path = Path(src)
        if not path.exists():
            if path.name == "jieba_userdict.txt":
                continue
            raise FileNotFoundError(path)
        args.extend(["--add-data", f"{path}{sep}{dest}"])
    return args


def build(clean: bool) -> None:
    if clean:
        shutil.rmtree(DIST_DIR, ignore_errors=True)
        shutil.rmtree(BUILD_DIR, ignore_errors=True)
        SPEC_PATH.unlink(missing_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--windowed",
        "--onedir",
        "--name",
        "SoundDesignFXName",
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(BUILD_DIR),
        "--specpath",
        str(SPEC_DIR),
        *(_add_data_args()),
        str(ROOT / "fxname_app.py"),
    ]
    print("running:", " ".join(f'"{x}"' if " " in x else x for x in cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)
    print(f"release folder: {DIST_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-clean", action="store_true", help="keep previous build artifacts")
    args = parser.parse_args()
    build(clean=not args.no_clean)


if __name__ == "__main__":
    main()
