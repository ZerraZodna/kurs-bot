# ⚠️ DEPRECATED: Embeddings & Trigger Matchers

> **This document is deprecated and kept for historical reference only.**
>
> The embedding-based trigger matching system described here has been **replaced by function calling**.
> 
> **See the new documentation:**
> - [FUNCTION_CALLING.md](./FUNCTION_CALLING.md) - Current function calling architecture
> - [FUNCTION_CALLING_MIGRATION_PLAN.md](./FUNCTION_CALLING_MIGRATION_PLAN.md) - Migration details
>
> **Migration completed:** All 5 phases finished. The `sentence-transformers` dependency has been removed,
> and the system now uses LLM-driven function calls for intent detection and action dispatch.

---

# Embeddings & Trigger Matchers — Overview (Historical)

This document describes the **legacy** embedding-based system that was used for trigger matching.
It is preserved for reference but no longer reflects the current architecture.

**Where to look in code**
- Embedding generation and utilities: `src/services/embedding_service.py`
- Trigger canonical data & seeding: `src/triggers/trigger_matcher.py` (STARTER)
- CI seeding / deterministic fallback: `scripts/ci_seed_triggers.py` and `scripts/ci_trigger_data.py`
- Trigger dispatch: `src/triggers/triggering.py` and `src/triggers/trigger_dispatcher.py`
- Trigger DB model: `src/models/database.py` (`TriggerEmbedding`)
- Semantic search: `src/services/semantic_search.py`
- Fast in-memory index (optional, added): `src/services/vector_index.py`
- Dev helpers: `scripts/debug_trigger.py` and `scripts/export_trigger_embeddings.py` (suggested exporter)

**High-level flow**
1. A central `EmbeddingService` (singleton) generates embeddings via one of two backends:
   - `local`: `sentence-transformers` (default model `SENTENCE_TRANSFORMERS_MODEL`, e.g. `all-MiniLM-L6-v2`)
   - `ollama`: HTTP embed endpoint configured via `OLLAMA_EMBED_URL` / `OLLAMA_EMBED_MODEL`
2. Canonical trigger utterances (the `STARTER` list in `trigger_matcher.py`) are embedded and stored in DB table `trigger_embeddings` as float32 bytes.
3. At runtime, incoming user text is embedded and compared to persisted trigger embeddings using cosine similarity. Top matches above a trigger's `threshold` are dispatched to the trigger dispatcher.
4. For performance, an in-memory vector index (FAISS if available, otherwise a normalized numpy matrix) is optionally built when triggers are loaded; matching falls back to brute-force cosine checks if index/search fails.

**Storage & serialization**
- Embeddings are serialized as float32 bytes using `numpy.ndarray.tobytes()` and converted back with `np.frombuffer(..., dtype=np.float32)`. See `EmbeddingService.embedding_to_bytes` / `bytes_to_embedding`.

**CI & deterministic seeding (no heavy ML deps required)**
- `scripts/ci_seed_triggers.py` is used by tests/CI to populate `trigger_embeddings`.
  - If `scripts/ci_trigger_data.py` exists (containing a `TRIGGERS` list of precomputed float arrays), CI will import that and insert the floats directly.
  - If `ci_trigger_data.py` is absent, `ci_seed_triggers.py` falls back to a deterministic `hash_embedding()` (SHA256-based) which produces stable, dependency-free unit-length vectors from utterance text.
- Tests seed triggers in `tests/conftest.py` (so CI and local test runs are reproducible without Ollama or sentence-transformers).

**⚠️ CRITICAL: Keeping `ci_trigger_data.py` in sync with STARTER**

The `STARTER` list in `trigger_matcher.py` is the canonical source of trigger
definitions. `scripts/ci_trigger_data.py` must contain precomputed embeddings
for ALL entries in STARTER. If STARTER is updated (new action types, new
phrases) but `ci_trigger_data.py` is not regenerated:

**Current STARTER action types** (as of 2025-06-26, 123 entries total):
`confirm_no` (5), `confirm_yes` (6), `create_schedule`, `enter_rag`, `exit_rag`,
`greeting` (11), `next_lesson`, `query_schedule`, `raw_lesson`, `set_timezone`,
`update_schedule`

**Regeneration command:**
```bash
ALLOW_EXPORT_PROD=1 .venv/bin/python scripts/export_trigger_embeddings.py \
  --from-starter --out scripts/ci_trigger_data.py
```

**Production DB sync**: The prod DB `trigger_embeddings` table must also be
updated when STARTER changes. Run `npm run seed_triggers` on the production
host after deploying updated `ci_trigger_data.py`. See also TODO.md for a
proposed startup failsafe that auto-detects stale trigger counts.

**Local development vs CI**
- Local dev: if you have `sentence-transformers` installed, set `EMBEDDING_BACKEND=local` (or leave default) and the local model will be used to compute runtime embeddings.
  - To produce CI-committed embeddings that match your local model, run an exporter locally (see suggested `scripts/export_trigger_embeddings.py`) to compute model embeddings for `STARTER` and write `scripts/ci_trigger_data.py`. Commit that file so CI imports exact float arrays.
- CI: intended to be dependency-free and uses `ci_trigger_data.py` if present, otherwise the deterministic SHA256 hashing fallback.

**Failover & offline operation**
- If no embedding backend is available at runtime (no Ollama, no sentence-transformers), `generate_embedding()` returns `None` and trigger matching will not match runtime queries. To ensure offline behavior you can:
  1. Run the local `sentence-transformers` model and install it on your runtime host.
 2. Precompute and commit `scripts/ci_trigger_data.py` so tests/CI use those floats.
 3. Add a deterministic keyword/fuzzy fallback for critical intents (e.g., detect "list|show" + "reminder|schedule|reminders") — simple but robust if you cannot compute embeddings at runtime.

**Component notes & pointers**
- `trigger_matcher.py`:
  - `seed_triggers()` embeds `STARTER` utterances and writes rows to DB.
  - `match_triggers()` obtains a query embedding (or accepts a `precomputed_embedding`) and returns top-k matches by cosine similarity.
  - There are many starter paraphrases (including localized phrases) to improve recall.
- `ci_seed_triggers.py`:
  - Prefers `scripts/ci_trigger_data.py` if present; else uses `hash_embedding()` deterministic fallback.
- `vector_index.py` (added):
  - Provides FAISS-based IndexFlatIP + IDMap when `faiss` is installed; otherwise uses normalized numpy matrix with dot-product search (equivalent to cosine on normalized vectors).
- `scripts/debug_trigger.py` (added):
  - Small helper to query the matcher; when run directly it forces the test DB env so it doesn't touch `prod.db`.

**How to reproduce / test locally**
1. (Optional) Install sentence-transformers:
   ```powershell
   pip install sentence-transformers numpy
   ```
2. (Optional) Create `scripts/ci_trigger_data.py` (export local model embeddings) by running an exporter script (see `scripts/export_trigger_embeddings.py` suggestion) and commit it for CI.
3. Run tests locally: `npm test` (the test runner will call the repository's venv/test harness and seed triggers as configured).

**Tuning & troubleshooting**
- Thresholds: per-trigger `threshold` field and global `TRIGGER_SIMILARITY_THRESHOLD` in settings control matching sensitivity. Start around `0.75` and tune based on logs.
- Logging: enable debug logs for `src.triggers.trigger_matcher` and `src.services.embedding_service` to inspect embedding dims, conversion errors, and match scores.
- If matches are missing: check that `generate_embedding()` returns a non-empty vector with the expected dimension; verify persisted embedding dimension matches runtime embedding dimension; check DB seeding.

## Trigger Tuning Workflow

1. Add or refine trigger phrases:
   - Edit `STARTER` in `src/triggers/trigger_matcher.py`.
   - Add paraphrases for the same action (especially natural variants and localized phrasing).
   - Keep `name`/`action_type` stable when adding variants for an existing intent.
2. Tune thresholds:
   - Set per-trigger `threshold` directly in `STARTER` entries.
   - Use `TRIGGER_SIMILARITY_THRESHOLD` as a global fallback when per-trigger threshold is missing.
   - Raise thresholds to reduce false positives, lower slightly to improve recall for paraphrases.
3. Inspect why a message matched or missed:
   - Use the runtime debug command:
     - `debug_trigger <message>`
     - `trigger_debug <message>`
   - The output includes matched action, score, threshold, fallback-path usage, and top candidate actions.
4. Verify with tests:
   - Trigger-focused tests:
     - `npm test -- tests/test_trigger_matcher.py tests/test_trigger_observability.py -q`
   - Dialogue fallback-order tests:
     - `npm test -- tests/test_lesson_trigger_order.py -q`
   - Scheduler integration tests:
     - `npm test -- tests/test_scheduler_service.py tests/test_trigger_scheduler_integration.py -q`
5. Re-check logs after tuning:
   - Structured trigger decision logs are emitted from `src/triggers/triggering.py` as `trigger_decision` lines.
   - For lesson raw-text decisions, `src/lessons/handler.py` logs whether semantic matching or regex fallback was used.

## Telegram Admin Commands (Trigger Embeddings)

These commands are available in chat for the configured Telegram admin only.

- `trigger_add <action_type> | <phrase> | <threshold_optional>`
  - Example: `trigger_add create_schedule | remind me after lunch | 0.66`
  - Adds one embedding phrase to an existing `action_type`.
- `trigger_list [action_type]`
  - Example: `trigger_list create_schedule`
  - Lists latest trigger rows (up to 50).
- `trigger_delete <trigger_id>`
  - Example: `trigger_delete 123`
  - Deletes one trigger row by id.

Authorization note:
- Commands are allowed only when the message sender matches the stored admin Telegram chat id.
- The admin chat id is set when a message arrives from `ADMIN_TELEGRAM_USERNAME` in webhook handling.

If you'd like, I can add the exporter script (`scripts/export_trigger_embeddings.py`) into the repo so you can generate `scripts/ci_trigger_data.py` locally and commit it. I can also add a short troubleshooting checklist to this doc.
