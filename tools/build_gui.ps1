# 打包独立测试前端为单应用（文件夹模式，dist/SoundDesignTranslator/）。
# 用法（仓库根目录）：  powershell -ExecutionPolicy Bypass -File tools/build_gui.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "安装 pyinstaller..." -ForegroundColor Yellow
    python -m pip install pyinstaller
}

Write-Host "开始打包（模型较大，约几分钟）..." -ForegroundColor Cyan
pyinstaller --noconfirm --clean translator_gui.spec

Write-Host "完成：dist\SoundDesignTranslator\SoundDesignTranslator.exe" -ForegroundColor Green
