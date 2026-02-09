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
        $cmd = Get-Command docker -ErrorAction SilentlyContinue
        if (-not $cmd) {
            Start-Sleep -Seconds $IntervalSeconds
            continue
        }
        try {
            docker info > $null 2>&1
            if ($LASTEXITCODE -eq 0) { return $true }
        } catch {
            # docker CLI exists but daemon not responding yet
        }
        Start-Sleep -Seconds $IntervalSeconds
    }
    return $false
}

if (-not (Wait-DockerReady -TimeoutSeconds 60 -IntervalSeconds 3)) {
    Write-Host "Docker CLI/daemon not available after waiting; please start Docker Desktop or ensure Docker is running." -ForegroundColor Yellow
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
