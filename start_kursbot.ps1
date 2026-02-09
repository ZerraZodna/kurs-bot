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

param(
	[switch]$StartInfra  # if set, will call scripts\start_all.ps1 before starting app/ngrok
)

function Resolve-VenvActivate {
	$candidate = Join-Path -Path (Get-Location) -ChildPath ".venv\Scripts\Activate.ps1"
	if (Test-Path $candidate) { return $candidate }
	return $null
}

$venvActivate = Resolve-VenvActivate
if (-not $venvActivate) {
	Write-Host ".venv not found. Create a virtualenv and install requirements first." -ForegroundColor Yellow
}

function Test-RedisRunning {
	try {
		$client = New-Object System.Net.Sockets.TcpClient
		$iar = $client.BeginConnect('127.0.0.1', 6379, $null, $null)
		$ok = $iar.AsyncWaitHandle.WaitOne(500)
		if (-not $ok) { $client.Close(); return $false }
		$client.EndConnect($iar)
		$client.Close()
		return $true
	} catch {
		return $false
	}
}

function Is-WorkerRunning {
	try {
		$procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue
		if (-not $procs) { return $false }
		foreach ($p in $procs) {
			if ($p.CommandLine) {
				if ($p.CommandLine -match 'rq\s+worker' -or $p.CommandLine -match 'rq.exe' -or $p.CommandLine -match 'rq\s') {
					return $true
				}
			}
		}
		return $false
	} catch {
		return $false
	}
}

# Decide whether to start infra. If user passed -StartInfra, always start. Otherwise
# only start infra when Redis or the worker process is not running.
$needStartInfra = $false
if ($StartInfra) {
	$needStartInfra = $true
} else {
	$redisOk = Test-RedisRunning
	$workerOk = Is-WorkerRunning
	if (-not $redisOk -or -not $workerOk) {
		Write-Host "Infra not fully running (Redis:$redisOk, Worker:$workerOk) - will start infra..."
		$needStartInfra = $true
	} else {
		Write-Host "Infra appears to be running (Redis:$redisOk, Worker:$workerOk)."
	}
}

if ($needStartInfra) {
	$startAll = Join-Path -Path (Get-Location) -ChildPath "scripts\start_all.ps1"
	if (Test-Path $startAll) {
		Write-Host "Starting infra (Redis, worker, reindex)..."
		& $startAll
	} else {
		Write-Host "scripts\start_all.ps1 not found; skipping infra start." -ForegroundColor Yellow
	}
}

# Wait helpers used only by this startup script
function Wait-ForTcpPort {
	param(
		[string]$Host = '127.0.0.1',
		[int]$Port,
		[int]$TimeoutSeconds = 30
	)
	$start = Get-Date
	while ((Get-Date) -lt $start.AddSeconds($TimeoutSeconds)) {
		try {
			$client = New-Object System.Net.Sockets.TcpClient
			$iar = $client.BeginConnect($Host, $Port, $null, $null)
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

function Wait-ForWorker {
	param([int]$TimeoutSeconds = 30)
	$start = Get-Date
	while ((Get-Date) -lt $start.AddSeconds($TimeoutSeconds)) {
		if (Is-WorkerRunning) { return $true }
		Start-Sleep -Seconds 1
	}
	return $false
}

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

# If we started infra, wait for Redis and the worker to become available
if ($needStartInfra) {
	Write-Host "Waiting for infra readiness checks..."
	$redisReady = Wait-ForTcpPort -Host '127.0.0.1' -Port 6379 -TimeoutSeconds 60
	if ($redisReady) { Write-Host "Redis is reachable." } else { Write-Host "Redis did not become reachable within timeout." -ForegroundColor Yellow }

	$workerReady = Wait-ForWorker -TimeoutSeconds 60
	if ($workerReady) { Write-Host "RQ worker process detected." } else { Write-Host "RQ worker not detected after timeout; check worker logs." -ForegroundColor Yellow }
}

# Wait for uvicorn to start responding on port 8000 (startup-only check)
$apiReady = Wait-ForTcpPort -Host '127.0.0.1' -Port 8000 -TimeoutSeconds 30
if ($apiReady) { Write-Host "Uvicorn is accepting connections on port 8000." } else { Write-Host "Uvicorn did not accept connections within timeout." -ForegroundColor Yellow }
