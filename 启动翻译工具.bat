@echo off
setlocal
cd /d "%~dp0"

where python.exe >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

if not exist "nllb_int8_model" (
    echo [ERROR] NLLB model missing: nllb_int8_model\
    pause
    exit /b 1
)

REM 最新测试前端：中->FXName / 中->英 / 英->中，模式可选
where pythonw.exe >nul 2>&1
if errorlevel 1 (
    python -B translator_gui.py
    if errorlevel 1 (
        pause
        exit /b 1
    )
    exit /b 0
)

start "" pythonw.exe -B translator_gui.py
exit /b 0
