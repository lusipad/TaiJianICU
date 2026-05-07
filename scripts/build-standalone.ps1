param(
    [string]$Python = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

if (-not (Test-Path $Python)) {
    $Python = "python"
}

& $Python scripts/build_standalone.py --python $Python

Write-Host ""
Write-Host "Standalone build finished:"
Write-Host "  $RepoRoot\dist\TaiJianICU.exe"
Write-Host ""
Write-Host "For non-developer users, put TaiJianICU.exe and .env next to each other."
