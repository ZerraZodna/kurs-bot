# Deployment Notes

This document describes recommended steps and considerations for deploying Kurs Bot (production).

1) Infrastructure components
- Postgres (or other production SQL) for application data. Configure `DATABASE_URL` in environment.
- Worker processes (if used) to process background tasks.
- Optional vector index (FAISS for local/batch or managed vector DB in production).

2) Environment variables (important)
- `DATABASE_URL` — production DB connection string.
- `OLLAMA_EMBED_URL` and `OLLAMA_EMBED_MODEL` — embedding service endpoint and model.
- `EMBEDDING_DIMENSION` — ensure this matches the embed model used.
  Note: vector-index configuration and runtime toggles were removed in this branch; vector indexing is disabled by design.
- `NGROK_PATH` — optional for local dev only.

3) Service startup order (recommended)
1. Start the database and run migrations (alembic).
2. Start background workers (if used) — at least 1 worker, scale horizontally for throughput.
4. Start the API (`uvicorn src.api.app:app`).

5) Rolling upgrades & reindex strategy
- This branch does not use a runtime feature flag for vector-index reads/writes; to reintroduce vector indexing follow the historical guidance and re-enable the appropriate code paths.
- To change embedding model or dimension:
  - Create a migration plan to regenerate embeddings: run a backfill via the queue in low-traffic windows.
  - Backfill embeddings if reintroducing persistence; workers should check existing metadata before regenerating.

6) Local development & CI
- CI: run `pytest` in a pipeline (see `.github/workflows/ci.yml`) — tests use SQLite and local vector `local` adapter so CI does not require external embeddings.

7) Security
- Protect embedding API keys and DB credentials via your secrets manager.
- Ensure GDPR and privacy controls are applied when exporting/importing memories.

8) Backups
- Regular DB backups and (if used) periodic dumps of the vector index.

Contact ops/backend team to finalize runtime sizing and alert thresholds before production roll-out.
