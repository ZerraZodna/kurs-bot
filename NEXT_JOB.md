# NEXT_JOB: Vector-index migration (embedding pipeline focus)

Goal
- Replace DB-scanning semantic search with a vector-index backed search pipeline.
- This job focuses only on the embedding generation and index upsert parts so
  the embedding worker can reliably produce vectors and optionally upsert them
  to a vector index (RedisVector or FAISS). Search replacement is a separate
  follow-up.

Scope
- Implement `src/services/vector_index.py` adapter (thin interface).
- Provide `upsert(id, vector)`, `bulk_upsert(iterable[(id, vector)])`, and
  `query(vector, k)` methods. Support backends: RedisVector (preferred) and
  FAISS (local test mode).
- Add reindex script that scans `memories` and enqueues missing/mismatched
  embeddings for generation and index upsert (uses existing `enqueue_embedding_for_memory`).
- Wire worker to optionally upsert when `VECTOR_INDEX_ENABLED=true` (already
  attempted; harden and test).

Why this next
- Embeddings generation and reliable upsert are prerequisites for a vector
  index migration. The worker is now capable of batch processing; adding a
  robust index client and reindex flow lets us run canaries and migrate with
  low blast radius.

Acceptance criteria
- `src/services/vector_index.py` exists and exposes `upsert`, `bulk_upsert`,
  `query` with a stable API and `from_env()` factory.
- Worker upserts vectors when `VECTOR_INDEX_ENABLED=true` and logs upsert
  successes/failures with metrics.
- `scripts/reindex_vectors.py --enqueue-missing` enqueues jobs for memories
  missing embeddings and `--bulk-upsert` can bulk-upsert existing embeddings.
- Integration test(s) that run locally against FAISS and a Redis instance
  (CI job spins up Redis) validating: an upsert, a query returns the expected
  IDs, and reindex enqueues missing embeddings.

High-level plan (phases)
1) Adapter + Local FAISS
   - Add `src/services/vector_index.py` with a `VectorIndexClient` base and
     `FaissVectorClient` implementation that runs locally (pure-Python).
   - Implement `from_env()` so tests can instantiate FAISS without Redis.
   - Unit tests for adapter API and `bulk_upsert` behavior using FAISS.

2) Redis Vector client
   - Implement `RedisVectorClient` using Redis/Redis-Stack vector commands
     (or `redis-py` module vector extension). Keep operations simple: upsert,
     query (top-k), bulk_upsert.
   - Add configuration/env var `VECTOR_INDEX_BACKEND=redis|faiss`.

3) Worker integration + metrics
   - Ensure `src/workers/embedding_worker.py` uses `VectorIndexClient.from_env()`
     when `VECTOR_INDEX_ENABLED=true` and records metrics on upsert latency and
     failures.
   - Add small retry around index upsert (non-blocking for embedding persistence).

4) Reindex script & CI
   - Enhance `scripts/reindex_vectors.py` to support `--bulk-upsert` and
     `--enqueue-missing` (already partly present). Add integration test(s)
     which spin up Redis in CI and validate overall flow.

5) Canary & rollout
   - Add feature flag / traffic split for search consumer to prefer vector
     index results when available; run canary tests comparing top-k results
     and latencies.

Risks & mitigations
- Risk: Redis vector availability/ops complexity. Mitigation: FAISS local
  fallback for dev; keep migration feature-flagged.
- Risk: Index and DB drift. Mitigation: reindex script with checksum/versions
  and run periodic reindex as necessary.

Estimates (rough)
- Phase 1 (adapter + FAISS): 1-2 days
- Phase 2 (Redis client): 1-2 days (depends on ops help/testing)
- Phase 3 (worker + metrics): 0.5-1 day
- Phase 4 (reindex + CI): 1 day

Immediate next actions (concrete)
1. Create `src/services/vector_index.py` with base class + FAISS client.
2. Add unit tests for `FaissVectorClient` and wire `scripts/reindex_vectors.py`
   to use it when `VECTOR_INDEX_BACKEND=faiss`.
3. Add a small CI job (optional next step) to start Redis and run integration
   tests for the Redis client.

Notes
- `scripts/reindex_vectors.py` already references `VectorIndexClient` — this
  file will integrate cleanly once `src/services/vector_index.py` exists.
