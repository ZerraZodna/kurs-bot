# Serve the dev web UI static files on a chosen static port and write a small
# runtime `config.js` that points the frontend to the backend API port.
# Usage: .\serve_dev_ui.ps1 -StaticPort 3000 -ApiPort 8000

param(
    [int]$StaticPort = 3000,
    [int]$ApiPort = 8000,
    [switch]$DirectApi
)

$repoRoot = Resolve-Path "$PSScriptRoot\.."
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$staticDir = Join-Path $repoRoot "static\dev_web_client"
$port = $StaticPort

Write-Host "Serving dev UI from" $staticDir "on port" $port "with API port" $ApiPort

# Write runtime config for the frontend to pick up the backend port.
# By default we leave `__DEV_API_BASE` empty so the client will POST to
# the relative `/dev/message` path which our static server proxies to the
# API backend. If `-DirectApi` is passed, write an explicit localhost URL
# (useful when running the frontend without the proxy).
$configPath = Join-Path $staticDir 'config.js'
if ($DirectApi) {
    $configContent = "window.__DEV_API_BASE = 'http://localhost:$ApiPort';"
} else {
    $configContent = "window.__DEV_API_BASE = '';"
}
Set-Content -Path $configPath -Value $configContent -Encoding UTF8

if (Test-Path $venvPython) {
    Write-Host "Using venv python:" $venvPython
    & $venvPython (Join-Path $repoRoot 'scripts\dev_static_server.py') --port $port --directory $staticDir --api-port $ApiPort
} else {
    Write-Host "Using system python"
    python (Join-Path $repoRoot 'scripts\dev_static_server.py') --port $port --directory $staticDir --api-port $ApiPort
}