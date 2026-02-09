<#
Start Redis (Docker), launch the RQ worker in a new window, then run an initial reindex.
This is a convenience script for local development after a clean install.
#>

param(
	[switch]$SkipReindex
)

# Load .env into environment so scripts pick up VECTOR_INDEX_BACKEND / VECTOR_INDEX_ENABLED
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
		if ($value.Length -ge 2) {
			if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
				$value = $value.Substring(1, $value.Length - 2)
			}
		}
		if (-not [string]::IsNullOrWhiteSpace($key)) { ${env:$key} = $value }
	}
}

Load-DotEnv

# Choose Redis starter based on VECTOR_INDEX_BACKEND (default: lightweight start_redis.ps1)
$backend = $env:VECTOR_INDEX_BACKEND
if ([string]::IsNullOrWhiteSpace($backend)) { $backend = 'local' }

Write-Host "VECTOR_INDEX_BACKEND=$backend"

if ($backend -in @('redis','redisstack','redis-stack')) {
	Write-Host "Starting Redis Stack (vector-enabled) via scripts/start_redis_stack.ps1..."
	.\scripts\start_redis_stack.ps1
} else {
	Write-Host "Starting lightweight Redis via scripts/start_redis.ps1..."
	.\scripts\start_redis.ps1
}

Write-Host "Starting worker..."
.\scripts\start_worker.ps1

if (-not $SkipReindex) {
	Write-Host "Running reindex (batch=100) in current window..."
	.\scripts\run_reindex.ps1 -batch 100
} else {
	Write-Host "Skipping reindex as requested."
}

Write-Host "Done."
