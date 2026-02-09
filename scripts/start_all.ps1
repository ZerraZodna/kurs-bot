<#
Start Redis (Docker), launch the RQ worker in a new window, then run an initial reindex.
This is a convenience script for local development after a clean install.
#>

param(
	[switch]$SkipReindex
)

Write-Host "Starting Redis (Docker)..."
.\scripts\start_redis.ps1

Write-Host "Starting worker..."
.\scripts\start_worker.ps1

if (-not $SkipReindex) {
	Write-Host "Running reindex (batch=100) in current window..."
	.\scripts\run_reindex.ps1 -batch 100
} else {
	Write-Host "Skipping reindex as requested."
}

Write-Host "Done."
