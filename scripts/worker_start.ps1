param(
    [string]$RedisUrl = "redis://localhost:6379"
)

$env:REDIS_URL = $RedisUrl
Write-Host "Starting RQ worker for 'embeddings' queue using REDIS_URL=$env:REDIS_URL"

# Use Python module invocation to ensure environment's rq is used
python -m rq worker embeddings --url $env:REDIS_URL
