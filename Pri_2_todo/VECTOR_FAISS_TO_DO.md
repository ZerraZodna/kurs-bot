# VECTOR FAISS To Do

Purpose
- Describe how to add optional native FAISS support to the project and why
  it's valuable for the RAG/search migration. This is focused on search/index
  infrastructure and not on prompt engineering or RAG prompt templates.

Why implement native FAISS
- Performance: FAISS provides high-throughput, low-latency approximate
  nearest-neighbor search (IVF/HNSW/OPQ) that scales beyond an in-process
  brute-force NumPy approach.
- Resource-efficiency: Real FAISS can use optimized BLAS, quantization and
  GPU acceleration to reduce memory and CPU cost for large collections.
- Production parity: Tests and canaries using native FAISS reduce surprises
  when moving from dev to production workloads.

Scope
- Add an optional integration layer that uses the real `faiss` Python
  package when available and falls back to the existing NumPy "faiss-like"
  implementation in `src/services/vector_index.py` when not present.
- Provide a clean factory or wrapper such as `FaissNativeClient` with the
  same `upsert`, `bulk_upsert`, `query`, and `from_env()` API so the rest
  of the codebase (workers, reindex script, semantic-search) is unchanged.
- Keep no runtime dependency on native FAISS unless `VECTOR_INDEX_BACKEND`
  is explicitly set to `faiss_native` (or similar). Default remains the
  pure-Python implementation used today.

Design notes
- Detect `faiss` import at runtime and provide a thin adapter that maps
  vector IDs and numpy arrays to FAISS indexes. Example strategy:
  - Use `faiss.IndexFlatIP` or `IndexFlatL2` for simple builds, and expose
    optional HNSW/IVF configuration via env vars.
  - Maintain a mapping of IDs to index positions (if using index types that
    don't directly store string IDs). Persist this mapping to disk or DB
    when needed for warm restarts.
  - Implement `upsert` as either `add_with_ids` (when supported) or remove
    + re-add semantics for updates.

Config / Env
- `VECTOR_INDEX_BACKEND=faiss_native|faiss|local|redis`
- `VECTOR_INDEX_FAISS_INDEX_TYPE=flat|ivf|hnsw` (optional)
- `VECTOR_INDEX_DIM` or reuse `EMBEDDING_DIMENSION`

Testing & Dev workflow (no Docker required)
- Local dev: install `faiss-cpu` into your Python environment (or use
  conda). For Windows, prefer conda builds; for Linux/macOS `pip install faiss-cpu`.
- Unit tests: add fast unit tests that exercise `FaissNativeClient` using
  small vectors (same tests as `tests/test_vector_index.py`) — they run
  with or without the native package; skip tests when `faiss` not present.
- Integration: optional larger tests that use native FAISS features can run
  on dev machines or in CI images that include FAISS (not required for
  normal CI runs).

Acceptance criteria
- `src/services/vector_index.py` (or a new module) exposes a `FaissNativeClient`
  with `upsert`, `bulk_upsert`, `query`, and `from_env()`.
- Worker behavior unchanged: when `VECTOR_INDEX_ENABLED=true` and
  `VECTOR_INDEX_BACKEND=faiss_native`, the worker upserts vectors and logs
  latencies as before.
- Tests: unit tests run locally with `faiss` when available and skip/cover
  fallback behavior when not.

Risks & mitigations
- Windows packaging complexity: recommend `conda` for Windows users and
  keep pure-Python fallback so Docker/FAISS are not required.
- Index persistence and ID mapping: store an ID->index mapping (simple
  pickle/json) or use `IndexIDMap`/`IndexIDMap2` wrappers provided by FAISS.

Rollout plan
1. Implement adapter + unit tests (feature-flagged). Keep fallback.
2. Run canary on a small dataset on a dev machine with `faiss-cpu`.
3. Optionally adopt optimized index parameters (IVF/HNSW) and tune.

Estimates
- Adapter + tests: 1 day
- Optional production tuning and persistence: 1-2 days

Next actions (concrete)
- Add `FaissNativeClient` wrapper that imports `faiss` only when used.
- Add small unit tests and CI job targeting a build that includes FAISS
  (optional, separate PR).
- Document local installation steps and conda recommendations in README.

Notes
- This work is focused on vector search/indexing for RAG search, not on
  prompt design or RAG prompt templates. The FAISS integration improves
  retrieval performance and quality, which in turn benefits any RAG system
  that relies on high-quality nearest-neighbor results.
