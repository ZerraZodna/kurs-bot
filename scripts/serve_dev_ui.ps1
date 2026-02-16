# Serve the dev web UI static files on a chosen static port and write a small
# runtime `config.js` that points the frontend to the backend API port.
# Usage: .\serve_dev_ui.ps1 -StaticPort 3000 -ApiPort 8000

param(
    [int]$StaticPort = 3000,
    [int]$ApiPort = 8000,
    [switch]$DirectApi,
    [switch]$Reload
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

function Start-DevServer {
    param($pythonExe)
    Write-Host "Starting dev static server using" $pythonExe
    & $pythonExe (Join-Path $repoRoot 'scripts\dev_static_server.py') --port $port --directory $staticDir --api-port $ApiPort
}

if (-not $Reload) {
    if (Test-Path $venvPython) {
        Write-Host "Using venv python:" $venvPython
        Start-DevServer -pythonExe $venvPython
    } else {
        Write-Host "Using system python"
        Start-DevServer -pythonExe python
    }
} else {
    Write-Host "Reload enabled: watching" $staticDir "for changes..."

    function Get-LatestWriteTime {
        param($dir)
        try {
            $items = Get-ChildItem -Path $dir -Recurse -File -ErrorAction Stop
            if (-not $items) { return $null }
            return ($items | Measure-Object -Property LastWriteTime -Maximum).Maximum
        } catch {
            return $null
        }
    }

    $lastWrite = Get-LatestWriteTime -dir $staticDir

    while ($true) {
        if (Test-Path $venvPython) {
            $proc = Start-Process -FilePath $venvPython -ArgumentList @( (Join-Path $repoRoot 'scripts\dev_static_server.py'), '--port', $port, '--directory', $staticDir, '--api-port', $ApiPort ) -NoNewWindow -PassThru
        } else {
            $proc = Start-Process -FilePath 'python' -ArgumentList @( (Join-Path $repoRoot 'scripts\dev_static_server.py'), '--port', $port, '--directory', $staticDir, '--api-port', $ApiPort ) -NoNewWindow -PassThru
        }

        # Poll for file changes or process exit
        while (-not $proc.HasExited) {
            Start-Sleep -Seconds 1
            $newWrite = Get-LatestWriteTime -dir $staticDir
            if ($newWrite -ne $null -and $lastWrite -ne $null -and $newWrite -gt $lastWrite) {
                Write-Host "Change detected in $staticDir; restarting dev server..."
                try { Stop-Process -Id $proc.Id -Force } catch { }
                break
            }
        }

        # Update lastWrite and loop to restart
        $lastWrite = Get-LatestWriteTime -dir $staticDir
        Start-Sleep -Seconds 1
    }
}