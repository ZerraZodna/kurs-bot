# Migration plan: vector search

Purpose: outline a future move from SQL‐stored embeddings to a proper ANN index (Faiss/HNSWlib or pgvector/hosted) for fast semantic search.

## Current state
- Trigger embeddings live in the `trigger_embeddings` SQL table as blobs; seeded deterministically via `scripts/ci_seed_triggers.py`. Size is small and acceptable.
- Optional local ANN path exists: `scripts/utils/embeddings_local.py` builds an HNSWlib file at `HNSWLIB_INDEX_PATH`, but the API does not load it today.
- Memory/lesson embeddings are not persisted as vectors in the app runtime; semantic search is limited.

## Why migrate
- SQL blob scans do not scale for real‑time similarity search.
- Need sub‑second retrieval across many users/memories.
- Want to avoid regenerating embeddings per request and reduce DB bloat.

## Target options
1) **Faiss or HNSWlib on disk (local)**
   - Store index file (e.g., `src/data/emb_index.bin`) alongside metadata.
   - Load on startup; rebuild offline when models change.
   - Fits single‑host/dev/edge deployments.
2) **pgvector in Postgres**
   - Store embeddings in a dedicated table with `vector` columns.
   - Good for multi‑tenant server deployments with managed Postgres.
3) **Hosted vector DB (Pinecone/Weaviate/etc.)**
   - Offloads scaling/ops; adds cost and external dependency.

## Data model changes (minimal)
- Introduce a `document_embeddings` table (or pgvector table) keyed by item id (e.g., memory_id/lesson_id) plus `namespace` (channel/user) and `updated_at`.
- Keep trigger embeddings in SQL for now; they are tiny and deterministic.
- Track `embedding_model` and `embedding_dim` for safe migrations.

## Migration sketch
1) **Prep**
   - Choose backend (Faiss file vs. pgvector) and define config keys.
   - Add loader abstraction: `VectorStore` interface with drivers for file/pgvector.
2) **Write path**
   - On embedding generation, upsert into the chosen vector store and record `embedding_model`.
3) **Read path**
   - Add vector search endpoint/service that queries the store; fallback to SQL/Numpy only in test mode.
4) **Backfill**
   - Batch encode existing memories/lessons; write to store.
   - Validate recall against a sample set.
5) **Cutover**
   - Default semantic search to the vector store; keep feature flag to fall back.
6) **Cleanup**
   - Remove unused blob columns/flags once stable; document rebuild procedures.

## Operational notes
- Rebuild jobs: run off‑peak; version embeddings by model hash.
- Backups: store index artifacts with metadata; for pgvector rely on regular DB backups.
- Monitoring: log load time and search latency; alert if index stale or missing.

## Open questions
- Which backend to standardize on (file vs. pgvector vs. hosted)?
- Expected corpus size and latency targets?
- How to shard by customer/workspace if size grows?
