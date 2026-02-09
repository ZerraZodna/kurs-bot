<#
.SYNOPSIS
  Start a local Redis container using Docker (creates container 'kursbot-redis').

USAGE
  .\scripts\start_redis.ps1
#>

$containerName = "kursbot-redis"

function Wait-DockerReady {
    param(
        [int]$TimeoutSeconds = 60,
        [int]$IntervalSeconds = 2
    )
    $start = Get-Date
    while ((Get-Date) -lt $start.AddSeconds($TimeoutSeconds)) {
        $now = Get-Date -Format o
        Write-Host "[$now] Wait-DockerReady: checking for 'docker' CLI..."
        $cmd = Get-Command docker -ErrorAction SilentlyContinue
        if (-not $cmd) {
            Write-Host "[$now] docker CLI not found in PATH. Waiting..."
            Start-Sleep -Seconds $IntervalSeconds
            continue
        }
        try {
            Write-Host "[$now] Running 'docker info' to check daemon..."
            docker info > $null 2>&1
            $code = $LASTEXITCODE
            Write-Host "[$now] 'docker info' exit-code: $code"
            if ($code -eq 0) { Write-Host "[$now] Docker daemon responding"; return $true }
        } catch {
            Write-Host "[$now] docker info threw: $($_.Exception.Message)" -ForegroundColor Yellow
        }
        Start-Sleep -Seconds $IntervalSeconds
    }
    return $false
}

if (-not (Wait-DockerReady -TimeoutSeconds 60 -IntervalSeconds 3)) {
    Write-Host "Docker CLI/daemon not available after waiting; please start Docker Desktop or ensure Docker is running." -ForegroundColor Yellow
    # Print some diagnostics to help debugging
    Write-Host "Diagnostics:"
    $dockCmd = Get-Command docker -ErrorAction SilentlyContinue
    if ($dockCmd) { Write-Host " docker path: $($dockCmd.Source)" } else { Write-Host " docker not found in PATH" }
    try { docker --version 2>&1 | Write-Host } catch { Write-Host "docker --version failed" }
    exit 1
}

$running = docker ps --filter "name=$containerName" --format "{{.Names}}"
if (-not $running) {
    $exists = docker ps -a --filter "name=$containerName" --format "{{.Names}}"
    if (-not $exists) {
        Write-Host "Creating and starting Redis container '$containerName'..."
        docker run -d --name $containerName -p 6379:6379 redis:7 | Out-Null
        Write-Host "Started Redis container '$containerName'."
    } else {
        Write-Host "Starting existing Redis container '$containerName'..."
        docker start $containerName | Out-Null
        Write-Host "Started existing container '$containerName'."
    }
} else {
    Write-Host "Redis container '$containerName' is already running."
}
