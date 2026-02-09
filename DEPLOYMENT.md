# Deployment Notes

This document describes recommended steps and considerations for deploying Kurs Bot (production).

1) Infrastructure components
- Postgres (or other production SQL) for application data. Configure `DATABASE_URL` in environment.
- Redis for background queue and optional vector index (Redis Stack recommended for managed vector features).
- Worker processes (RQ) to process embedding jobs and other background tasks.
- Optional vector index (FAISS for local/batch, Redis Vector or managed vector DB in production).

2) Environment variables (important)
- `DATABASE_URL` — production DB connection string.
- `REDIS_URL` — Redis connection string (e.g. redis://redis:6379).
- `OLLAMA_EMBED_URL` and `OLLAMA_EMBED_MODEL` — embedding service endpoint and model.
- `EMBEDDING_DIMENSION` and `EMBEDDING_VERSION` — ensure these match the embed model used.
- `VECTOR_INDEX_BACKEND` — 'redis' or 'local' (use 'redis' in prod with Redis Stack).
- `VECTOR_INDEX_ENABLED` — set to `true` when the vector-index infra is ready.
- `NGROK_PATH` — optional for local dev only.

3) Service startup order (recommended)
1. Start the database and run migrations (alembic).
2. Start Redis (or Redis Stack) and ensure it's reachable.
3. Start background workers (RQ) — at least 1 worker, scale horizontally for throughput.
4. Run `scripts/reindex_vectors.py --batch N` (or via `scripts/run_reindex.ps1`) to populate vector index from DB.
5. Start the API (`uvicorn src.api.app:app`).

4) Rolling upgrades & reindex strategy
- Use feature flags before enabling vector-index reads/writes (`VECTOR_INDEX_ENABLED`).
- To change embedding model or dimension:
  - Create a migration plan to regenerate embeddings: run a backfill via the queue in low-traffic windows.
  - Set `EMBEDDING_VERSION` and backfill; workers should check `embedding_version` before regenerating.

Redis Stack quickstart (local)

If you're testing the vector index locally, Redis Stack provides vector capabilities without extra infra. Quick Docker-based setup:

1. Minimal `docker-compose.yml` (create in repo root):

```yaml
version: '3.8'
services:
  redisstack:
    image: redis/redis-stack:latest
    ports:
      - '6379:6379'
      - '8001:8001' # (optional) RedisInsight web UI
    restart: unless-stopped
    volumes:
      - redisdata:/data

volumes:
  redisdata:
```

2. Start Redis Stack:

```powershell
docker compose up -d
```

3. Update your `.env` (or environment) before starting services:

```dotenv
VECTOR_INDEX_BACKEND=redis
VECTOR_INDEX_ENABLED=true
REDIS_URL=redis://localhost:6379
```

4. Populate the index from the DB (reindex):

```powershell
.\scripts\run_reindex.ps1 --batch 100
# or
python scripts/reindex_vectors.py --batch 100
```

Canary & cutover checklist

- Provision Redis/Redis Stack and ensure connectivity from API and workers.
- Enable `VECTOR_INDEX_ENABLED` in a canary deployment that receives a small percentage of traffic.
- Run `scripts/reindex_vectors.py --batch N` to populate vectors before enabling reads.
- Compare semantic-search latency and results between DB-scan and vector-index on canary users.
- Monitor queue length, upsert latency, and search hit-rates; roll back by toggling `VECTOR_INDEX_ENABLED`.

Notes
- Use `local` backend for CI and development where persistence and scale are not required.
- FAISS is useful for local benchmarking or batch reindexing but is in-process and not networked.

5) Monitoring & observability
- Collect metrics: queue length, job success/failure counts, embedding API latency, embedding age, vector index size, semantic-search latency.
- Log structured events for embedding jobs (job_id, user_id, memory_ids, duration, retries).
- Add alerts for elevated failure rate or long queue times.

6) Cost & rate controls
- Add rate-limiting at worker-level for calls to embedding providers (token-bucket or Redis-based limiter).
- Implement exponential backoff on transient failures and max-retries for jobs.

7) Local development & CI
- Use the provided `scripts/start_all.ps1`, `scripts/start_redis.ps1`, and `scripts/run_reindex.ps1` for local setup on Windows.
- CI: run `pytest` in a pipeline (see `.github/workflows/ci.yml`) — tests use SQLite and local vector `local` adapter so CI does not require external embeddings.

8) Security
- Protect embedding API keys and DB credentials via your secrets manager.
- Ensure GDPR and privacy controls are applied when exporting/importing memories.

9) Backups
- Regular DB backups and (if used) periodic dumps of the vector index.

Contact ops/backend team to finalize runtime sizing and alert thresholds before production roll-out.
