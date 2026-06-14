@echo off
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

if not exist "nllb_int8_model\model.bin" (
    echo [ERROR] Model missing: nllb_int8_model\model.bin
    pause
    exit /b 1
)

start "" pythonw "%~dp0app.py"
exit /b 0
