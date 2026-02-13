$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptRoot

# Minimal headless start script
$uvicornCmd = "uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000"
$ngrokCmd = "ngrok http 8000"

# Start ngrok in background (no venv activation required)
$ngrokOut = Join-Path $scriptRoot "ngrok.out.log"
$ngrokErr = Join-Path $scriptRoot "ngrok.err.log"
if (Get-Command 'bash' -ErrorAction SilentlyContinue) {
    Start-Process -FilePath 'bash' -ArgumentList '-lc', "nohup $ngrokCmd > '$ngrokOut' 2> '$ngrokErr' &" -WorkingDirectory $scriptRoot | Out-Null
} else {
    Start-Process -FilePath 'pwsh' -ArgumentList '-NoProfile', '-Command', "$ngrokCmd" -RedirectStandardOutput $ngrokOut -RedirectStandardError $ngrokErr -WorkingDirectory $scriptRoot | Out-Null
}
Write-Output "Started ngrok detached (stdout: $ngrokOut, stderr: $ngrokErr)"

# Run uvicorn in the foreground so logs appear directly in this terminal
if (Get-Command 'bash' -ErrorAction SilentlyContinue) {
    Write-Output "Starting uvicorn in foreground (activate venv if needed)"
    bash -lc "source '$scriptRoot/.venv/bin/activate' && $uvicornCmd"
} else {
    # Fallback to pwsh inline
    $activate = Join-Path $scriptRoot ".venv/bin/Activate.ps1"
    Write-Output "Starting uvicorn in foreground via pwsh"
    & pwsh -NoProfile -Command "& '$activate'; $uvicornCmd"
}
