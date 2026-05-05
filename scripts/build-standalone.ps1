param(
    [string]$Python = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

if (-not (Test-Path $Python)) {
    $Python = "python"
}

& $Python -m pip install -e . pyinstaller

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --name TaiJianICU `
    --onefile `
    --windowed `
    --add-data "webapp/static;webapp/static" `
    --add-data "config/prompts;config/prompts" `
    --add-data "config/references;config/references" `
    --collect-all lightrag `
    --collect-all litellm `
    --collect-all deepeval `
    --collect-all instructor `
    --collect-all langchain_text_splitters `
    --collect-all langgraph `
    --hidden-import webapp.app `
    --hidden-import cli.main `
    --hidden-import cli.standalone_cmd `
    --hidden-import PySide6.QtWebEngineCore `
    --hidden-import PySide6.QtWebEngineWidgets `
    "scripts/standalone_entry.py"

$DistDir = Join-Path $RepoRoot "dist"
$EnvExample = Join-Path $RepoRoot ".env.example"
if (Test-Path $EnvExample) {
    Copy-Item $EnvExample (Join-Path $DistDir ".env.example") -Force
}

Write-Host ""
Write-Host "Standalone build finished:"
Write-Host "  $DistDir\TaiJianICU.exe"
Write-Host ""
Write-Host "For non-developer users, put TaiJianICU.exe and .env next to each other."
