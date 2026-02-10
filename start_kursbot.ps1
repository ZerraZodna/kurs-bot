<#
start_kursbot.ps1

Improved startup helper for local development.

What it does:
- Verifies and activates the virtualenv when launching processes in new windows.
- Starts `uvicorn` in its own PowerShell window so logs remain visible.
- Starts `ngrok` in a new PowerShell window. The `NGROK_PATH` environment variable
  can be used to override the executable path.

Usage: run the script from the repository root: `.\
un_kursbot.ps1` or `.\start_kursbot.ps1`
#>

param()

# Load .env into environment so scripts and child processes inherit settings
function Load-DotEnv {
	$envFile = Join-Path -Path (Get-Location) -ChildPath ".env"
	if (-not (Test-Path $envFile)) { return }
	Get-Content $envFile | ForEach-Object {
		$line = $_.Trim()
		if ([string]::IsNullOrWhiteSpace($line)) { return }
		if ($line.StartsWith('#')) { return }
		$parts = $line -split '=', 2
		if ($parts.Count -lt 2) { return }
		$key = $parts[0].Trim()
		$value = $parts[1].Trim()
		# strip surrounding single or double quotes
		if ($value.Length -ge 2) {
			if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
				$value = $value.Substring(1, $value.Length - 2)
			}
		}
		if (-not [string]::IsNullOrWhiteSpace($key)) { ${env:$key} = $value }
	}
}

Load-DotEnv

function Resolve-VenvActivate {
	$candidate = Join-Path -Path (Get-Location) -ChildPath ".venv\Scripts\Activate.ps1"
	if (Test-Path $candidate) { return $candidate }
	return $null
}

$venvActivate = Resolve-VenvActivate
if (-not $venvActivate) {
	Write-Host ".venv not found. Create a virtualenv and install requirements first." -ForegroundColor Yellow
}

# externally. This script focuses on starting the app and optional ngrok.

# Wait helpers used only by this startup script
function Wait-ForTcpPort {
	param(
		[string]$HostName = '127.0.0.1',
		[int]$Port,
		[int]$TimeoutSeconds = 30
	)
	$start = Get-Date
	while ((Get-Date) -lt $start.AddSeconds($TimeoutSeconds)) {
		try {
			$client = New-Object System.Net.Sockets.TcpClient
			$iar = $client.BeginConnect($HostName, $Port, $null, $null)
			$ok = $iar.AsyncWaitHandle.WaitOne(500)
			if ($ok) {
				$client.EndConnect($iar)
				$client.Close()
				return $true
			}
			$client.Close()
		} catch {
			# ignore
		}
		Start-Sleep -Seconds 1
	}
	return $false
}

# Worker readiness check removed; function deleted.
# Build activation fragment used when launching new windows so each window activates the venv
$activateFragment = $null
if ($venvActivate) {
	$escaped = $venvActivate -replace "'","''"
	$activateFragment = "& '$escaped';"
}

# Resolve a PowerShell executable to use for new windows (pwsh -> powershell)
$shellExe = $null
$pwshCmd = Get-Command pwsh -ErrorAction SilentlyContinue
if ($pwshCmd) { $shellExe = $pwshCmd.Source }
if (-not $shellExe) {
	$psCmd = Get-Command powershell -ErrorAction SilentlyContinue
	if ($psCmd) { $shellExe = $psCmd.Source }
}
if (-not $shellExe) {
	Write-Host "No PowerShell executable (pwsh/powershell) found in PATH; cannot start new windows." -ForegroundColor Red
} else {
	# Start uvicorn in its own window (keeps logs)
	$uvicornCmd = "{0} uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000 --log-level debug" -f $activateFragment
	Write-Host "Starting uvicorn in a new PowerShell window using $shellExe..."
	Start-Process -FilePath $shellExe -ArgumentList @('-Command', $uvicornCmd) -WorkingDirectory (Get-Location)
}

# Start ngrok in its own window. Allow overriding via NGROK_PATH env var.
$ngrokPath = $env:NGROK_PATH
if ([string]::IsNullOrWhiteSpace($ngrokPath)) {
	# default path (user-specific); leave as-is if not available
	$ngrokPath = "C:\Users\steen\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe"
}

if (Test-Path $ngrokPath) {
	$ngrokCmd = "& '$ngrokPath' http 8000"
	Write-Host "Starting ngrok in a new PowerShell window..."
	if ($shellExe) {
		Start-Process -FilePath $shellExe -ArgumentList @('-Command', $ngrokCmd) -WorkingDirectory (Get-Location)
	} else {
		Write-Host "Cannot start ngrok in new window because no PowerShell executable was found; please start ngrok manually:" -ForegroundColor Yellow
		Write-Host $ngrokCmd
	}
} else {
	Write-Host "ngrok executable not found at '$ngrokPath'. Set NGROK_PATH or install ngrok if you need external tunneling." -ForegroundColor Yellow
}
Write-Host "Kurs Bot helper started. Uvicorn and ngrok are running in separate windows."

# Infra readiness checks removed.

# Wait for uvicorn to start responding on port 8000 (startup-only check)
	$apiReady = Wait-ForTcpPort -HostName '127.0.0.1' -Port 8000 -TimeoutSeconds 30
if ($apiReady) { Write-Host "Uvicorn is accepting connections on port 8000." } else { Write-Host "Uvicorn did not accept connections within timeout." -ForegroundColor Yellow }
