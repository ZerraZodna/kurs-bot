<#
Start an RQ worker for the `embeddings` queue in a new PowerShell window.
The script will try to activate .venv if present.

Usage: .\scripts\start_worker.ps1
#>

$venvActivate = Join-Path -Path (Get-Location) -ChildPath ".venv\Scripts\Activate.ps1"

if (Test-Path $venvActivate) {
    $activateEscaped = $venvActivate -replace "'","''"
    $cmd = "& '$activateEscaped'; rq worker embeddings --url redis://localhost:6379"
} else {
    $cmd = "rq worker embeddings --url redis://localhost:6379"
}

# Resolve available PowerShell executable (pwsh or powershell)
$shellExe = $null
$pwshCmd = Get-Command pwsh -ErrorAction SilentlyContinue
if ($pwshCmd) { $shellExe = $pwshCmd.Source }
if (-not $shellExe) {
    $psCmd = Get-Command powershell -ErrorAction SilentlyContinue
    if ($psCmd) { $shellExe = $psCmd.Source }
}

Write-Host "Starting RQ worker in new PowerShell window..."
if ($shellExe) {
    Start-Process -FilePath $shellExe -ArgumentList @('-Command', $cmd) -WorkingDirectory (Get-Location)
} else {
    Write-Host "No PowerShell executable found; running worker inline in this shell."
    iex $cmd
}
