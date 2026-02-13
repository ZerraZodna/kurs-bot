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
# Try to query ngrok's local API to display the public URL(s) so users can verify
# the tunnel is up. Retry for a short while because ngrok may take a moment to
# start when launched detached.
$ngrokApi = 'http://127.0.0.1:4040/api/tunnels'
$maxAttempts = 15
$attempt = 0
$tunnels = $null
while ($attempt -lt $maxAttempts -and -not $tunnels) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-RestMethod -Uri $ngrokApi -Method Get -ErrorAction Stop
        if ($resp.tunnels -and $resp.tunnels.Count -gt 0) {
            $tunnels = $resp.tunnels
            break
        }
    } catch {
        # ignore connection errors while ngrok starts
    }
    $attempt++
}
if ($tunnels) {
    Write-Output "ngrok tunnels found:"
    foreach ($t in $tunnels) {
        Write-Output "- Name: $($t.name) | Public URL: $($t.public_url) | Proto: $($t.proto)"
    }
} else {
    Write-Warning "Could not query ngrok API at $ngrokApi after $maxAttempts seconds. Check $ngrokErr for errors."
}
if (Get-Command 'bash' -ErrorAction SilentlyContinue) {
    Write-Output "Starting uvicorn in foreground (activate venv if needed)"
    # Use exec so the shell is replaced by the uvicorn process and SIGINT/Ctrl-C
    # is delivered directly to uvicorn (not swallowed by an intermediate shell).
    bash -lc "source '$scriptRoot/.venv/bin/activate' && exec $uvicornCmd"
} else {
    # We're already running inside pwsh -> activate the venv in this session and
    # run uvicorn directly so Ctrl-C is forwarded to the server process.
    $activate = Join-Path $scriptRoot ".venv/bin/Activate.ps1"
    Write-Output "Starting uvicorn in foreground via pwsh"
    . $activate
    & $uvicornCmd
}
