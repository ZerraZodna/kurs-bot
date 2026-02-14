<#
.SYNOPSIS
    Initialize a CLEAN new host: create prod DB and seed defaults.

.DESCRIPTION
    This PowerShell script is a thin wrapper that enforces safety checks
    and then calls the Python initializer under scripts/utils.

    Usage (from repo root):
      .\scripts\setup_new_host.ps1 -Yes
      .\scripts\setup_new_host.ps1 -Yes -Lessons src/data/\"Sparkly ACIM lessons-extracted.pdf\"
#>

param(
    [switch]$Yes,
    [string]$Lessons
    ,[switch]$InstallDeps
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ProdDb = Join-Path $RepoRoot 'src\data\prod.db'

if (Test-Path $ProdDb) {
    Write-Host "⚠️ Detected existing production DB at $ProdDb. This setup script is intended for CLEAN new hosts only. Aborting." -ForegroundColor Yellow
    Write-Host "If you want to initialize or reset prod DB intentionally, run: python scripts/utils/init_db.py --yes --db src/data/prod.db"
    exit 1
}

if (-not $Yes) {
    Write-Host "This script performs a full initialization intended for a CLEAN new host.`nRe-run with -Yes to proceed." -ForegroundColor Cyan
    exit 2
}

Write-Host "`n==> Initializing production database and seeding defaults"

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { Write-Host "python not found in PATH"; exit 3 }

if ($InstallDeps) {
    Write-Host "==> Installing dependencies: CPU-only PyTorch, sentence-transformers, hnswlib, and requirements"
    & $python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch
    if ($LASTEXITCODE -ne 0) { Write-Host "Failed to install torch"; exit $LASTEXITCODE }

    & $python -m pip install --no-cache-dir sentence-transformers hnswlib
    if ($LASTEXITCODE -ne 0) { Write-Host "Failed to install sentence-transformers/hnswlib"; exit $LASTEXITCODE }

    & $python -m pip install --no-cache-dir -r (Join-Path $RepoRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { Write-Host "Failed to install requirements.txt"; exit $LASTEXITCODE }
}

$initArgs = @("--yes", "--db", "src/data/prod.db")
if ($Lessons) { $initArgs += "--lessons"; $initArgs += $Lessons }

& $python (Join-Path $RepoRoot 'scripts\utils\init_db.py') $initArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[X] Setup completed"
