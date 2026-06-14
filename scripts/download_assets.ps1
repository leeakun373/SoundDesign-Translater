# 从 GitHub Release 下载大文件（模型 + 预构建术语库）

param(
    [string]$Tag = "v1.0.0",
    [string]$Repo = "leeakun373/SoundDesign-Translater"
)

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Downloading release assets from $Repo $Tag ..."

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] GitHub CLI (gh) not found. Install: https://cli.github.com/"
    exit 1
}

gh release download $Tag --repo $Repo --dir "$env:TEMP\sdt-release"

$ModelZip = Get-ChildItem "$env:TEMP\sdt-release\nllb_int8_model*.zip" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($ModelZip) {
    Write-Host "Extracting model to nllb_int8_model/ ..."
    Expand-Archive -Force $ModelZip.FullName -DestinationPath $Root
} else {
    Write-Host "[WARN] nllb_int8_model.zip not found in release"
}

$DbFile = Get-ChildItem "$env:TEMP\sdt-release\audio_glossary*.sqlite*" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($DbFile) {
    Copy-Item $DbFile.FullName "$Root\glossary\audio_glossary.sqlite" -Force
    Write-Host "Copied audio_glossary.sqlite"
} else {
    Write-Host "Building glossary from sources ..."
    python glossary/build_glossary.py
}

Write-Host "Done. Run: build_glossary.bat (if needed) then launch GUI."
