<#
Start Redis Stack (includes Redis Vector) via Docker.
Usage: .\scripts\start_redis_stack.ps1
#>

$containerName = "kursbot-redis-stack"

function Wait-DockerReady {
    param(
        [int]$TimeoutSeconds = 60,
        [int]$IntervalSeconds = 3
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
        Write-Host "Creating and starting Redis Stack container '$containerName'..."
        docker run -d --name $containerName -p 6379:6379 -p 8001:8001 redis/redis-stack:latest | Out-Null
        Write-Host "Started Redis Stack container '$containerName'."
    } else {
        Write-Host "Starting existing Redis Stack container '$containerName'..."
        docker start $containerName | Out-Null
        Write-Host "Started existing container '$containerName'."
    }
} else {
    Write-Host "Redis Stack container '$containerName' is already running."
}
