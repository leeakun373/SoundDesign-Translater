@echo off
setlocal
cd /d "%~dp0"

where python.exe >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

if not exist "glossary\audio_glossary.sqlite" (
    echo [ERROR] Glossary missing: glossary\audio_glossary.sqlite
    echo Run build_glossary.bat first.
    pause
    exit /b 1
)

python -B -c "from fxengine.ui import main" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] FXName Engine startup check failed.
    echo Run: python -m fxengine.ui
    pause
    exit /b 1
)

where pythonw.exe >nul 2>&1
if errorlevel 1 (
    python -B -m fxengine.ui
    if errorlevel 1 (
        pause
        exit /b 1
    )
    exit /b 0
)

start "" pythonw.exe -B -m fxengine.ui
exit /b 0
