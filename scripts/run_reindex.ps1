<#
Run the Python reindex script using the project's virtualenv if present.
Usage: .\scripts\run_reindex.ps1 --batch 100 --enqueue-missing
#>

param(
    [int]$batch = 100,
    [switch]$enqueueMissing
)

$venvActivate = Join-Path -Path (Get-Location) -ChildPath ".venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    Write-Host "Activating .venv and running reindex..."
    & $venvActivate
}

$args = "--batch $batch"
$argList = @('--batch', $batch.ToString())
if ($enqueueMissing) { $argList += '--enqueue-missing' }

& python .\scripts\reindex_vectors.py $argList
