# WORK IN PROGRESS: Background embedding worker

Status: Draft

Summary
- Replace ad-hoc `loop.create_task` / `asyncio.run` embedding calls with a resilient background worker to handle embedding generation asynchronously, reliably, and observably.
- Integrates with `src/services/embedding_service.py` to centralize embedding logic and improve retry, rate-limiting, batching, and monitoring.

Goals
- Reliable retries with exponential backoff for transient failures.
- Rate-limiting and batching to respect external embedding provider quotas.
- Visibility: job queue metrics, success/failure counts, per-user queue length, last-embedding timestamp.
- Easy local development and simple production deployment.

Non-goals
- Replacing existing vector index or semantic search implementation (this focuses only on embedding generation pipeline).

Requirements
- Worker must accept job payloads describing which memory (or set of memories) to embed.
- Worker must call `src/services/embedding_service.py` API surface (e.g., `embed_text`, `batch_embed`, or `upsert_memory_embeddings`) rather than reimplementing embedding logic.
- Jobs must be idempotent or include safeguards to avoid duplicate writes.
- Support for both immediate (sync) and queued (async) embedding flows.

Design options (pick one as default)
- RQ (Redis Queue)
  - Pros: Simple, lightweight, easy to run locally, good for Python stacks.
  - Cons: Less feature-rich than Celery, but sufficient for embedding jobs.
- Celery (with Redis/RabbitMQ)
  - Pros: Battle-tested, robust scheduling, advanced routing, time limits.
  - Cons: More operational overhead.
- fast-worker (fastapi + fast-worker)
  - Pros: Modern, async-friendly, integrated with FastAPI deployments.
  - Cons: Newer; evaluate maturity for retry semantics.

Recommendation
- Start with RQ for a quick iteration and migration path; implement an adapter layer so switching to Celery later is straightforward.

Job payload schema (example)
```
{
  "job_id": "uuid",
  "user_id": 123,
  "memory_ids": [345, 346],           # or a batch token
  "priority": "normal",             # optional
  "attempt": 0,
  "meta": {"source": "onboarding"}
}
```

Integration points
- Producer: replace `loop.create_task` / `asyncio.run` calls with `enqueue_embedding_job(job_payload)` helper.
  - Provide a thin helper in `src/services/embedding_service.py` or `src/services/embedding_worker.py` to enqueue jobs.
- Consumer: worker process reads job payload and calls `embedding_service.batch_embed(...)` and persists embedding bytes (or floats) back to DB via existing repository helpers.

Idempotency & concurrency
- Store job status on the `Memory` row or a separate `embedding_jobs` table keyed by memory_id + embedding_version.
- Worker should check whether embeddings are already present / up-to-date before performing expensive calls.

Retries, backoff & rate limiting
- Use RQ/Celery retry features with exponential backoff for transient errors.
- Implement token-bucket or leverage Redis rate-limiter to limit calls-per-minute per API key / org.
- Batch small jobs together within a short window (e.g., 100–200ms) to use `batch_embed` endpoints.

Observability
- Emit metrics: `embedding_jobs_enqueued`, `embedding_jobs_processed`, `embedding_jobs_failed`, `embedding_api_latency_ms`, `embedding_batch_size`.
- Add logs with structured fields: job_id, user_id, memory_ids, duration, retries.
- Track last_successful_embedding_timestamp on the `Memory` or user record.

Testing strategy
- Unit tests for enqueue helper and job payload validation.
- Integration tests using a local Redis + fake embedding API to verify retries, rate-limiting, and idempotency.
- E2E test: create a few Memory rows, enqueue jobs, run worker, assert embeddings saved and metrics emitted.

Migration & rollout
- Phase 1: Add enqueue helper and configuration toggle to use queue or inline calls.
- Phase 2: Flip setting to enqueue by default for non-critical memories.
- Phase 3: Migrate heavy backfill into queued worker with rate limiting.

Developer ergonomics
- Provide a `scripts/worker_start.sh` or PowerShell script to start a local worker and a small management command to requeue failed jobs.
- Document local workflows in repository README and in this doc.

Security & cost controls
- Validate job payloads to avoid accidental massive backfills.
- Add per-organization rate limits and spend alarms.

Next steps (concrete)
1. Add enqueue helper in `src/services/embedding_service.py` that wraps chosen queue client.  
2. Implement an RQ worker `src/services/embedding_worker.py` to process payloads and call `batch_embed`.  
3. Add metrics + logging.  
4. Add unit and integration tests under `tests/` and update CI to spin up Redis for those tests.
5. Backfill script using queue for existing memories.

References
- See `src/services/embedding_service.py` for current embedding logic and helper functions.

Open questions
- Which queue backend does ops prefer (Redis vs RabbitMQ)?  
- Should we support priority queues for immediate-onboarding embeddings?
- Do we want a separate `embedding_jobs` table for strict auditability or lean on memory row flags?

Contact
- Pair with backend/ops to choose deployment pattern and fill production config secrets for rate-limiter keys.


Vector-index migration (recommended as separate step)
- Keep embedding generation and queueing as a first-class job (see above). Once worker is stable, migrate search to a vector index.
- Migration approach (incremental):
  1. Feature-flag vector index writes from workers via `VECTOR_INDEX_ENABLED` (default `false`).
  2. Implement `src/services/vector_index.py` as a thin adapter with `upsert(id, vector)`, `query(vector, k)`, and `bulk_upsert(iterable)` methods. Support RedisVector, FAISS (local), or other backends.
  3. Add a reindex script that scans `memories` and enqueues missing/mismatched embeddings for generation and index upsert.
  4. Change `src/services/semantic_search.py` to prefer the vector index and fall back to DB-scanning + LLM re-rank when vector results are empty or stale.
  5. Run canary traffic (small % of users) against vector-index search and compare results/latency before full cutover.

Decision guidance
- Keep the migration as a separate deployable step to reduce blast radius. The worker should optionally upsert into the vector index so the migration can be rolled forward without changing producer code.
- Redis Vector is a pragmatic first choice for production (managed Redis or Redis Stack provides vector capabilities). FAISS is great for local experiments and batch reindexing.


