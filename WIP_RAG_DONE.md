```markdown
# WIP: RAG Improvements

Performance & scaling
- Move from scanning all `memories` rows to a vector index (FAISS / Annoy / Redis Vector) with a sync job to ingest memory embeddings. Keep DB copy for auditability.
- Batch embedding + rate-limiting and exponential backoff to avoid embedding service overload.

Observability & metrics
- Track embedding generation success/error, queue lengths, embedding age, semantic search latency, top similarity histogram, and usage counts of each prompt template.

Implementation roadmap (minimal viable steps)
5. (Optional) Add a small admin UI or management script to add curated prompts.

Further/Optional Enhancements
- Prompt templates marketplace: shareable templates between users/orgs (requires moderation and privacy considerations).
- Hybrid search + LLM rerank: if embeddings missing, return a candidate set using text search then re-rank via LLM.
- Auditable prompt usages: store which prompt version was used for each reply (useful for debugging and compliance).

Prioritized Recommendations (Priority 1 = High, Priority 2 = Medium)

Priority 1 (High)
- Background job queue for embedding generation: replace ad-hoc `loop.create_task` / `asyncio.run` with a resilient worker (RQ/Celery/fast-worker) to retry, rate-limit, and monitor embedding jobs; integrates with `src/services/embedding_service.py`.
- Use a vector index for search: move from loading all `Memory` rows and computing cosine similarities in-Python to a vector index (FAISS, Annoy, or Redis Vector DB) to reduce latency and scale. See `src/services/semantic_search.py`.
- Graceful fallback when embeddings missing: if embeddings are absent for a user, fall back to lightweight text search and LLM re-rank (use `rerank_memories`) so RAG still functions for new users.
- Expose RAG status & controls to users: surface `rag_mode_enabled` and last-used memory-count via a `rag_status` debug command or a short status reply.
- Show used memories (optional debug snippets): offer an opt-in short summary of the top N memories used for a response to increase transparency and trust (hook into `DialogueEngine.process_message`).
- Observability & metrics: track embedding generation success/failure, search latency, and similarity distribution (Prometheus / logs) to surface UX-impacting issues.

Priority 2 (Medium)
- Embedding versioning & migration: add scripts and tooling to re-generate or migrate embeddings when `embedding_version` or `EMBEDDING_DIMENSION` changes; log mismatches clearly.
- Batch & rate-limit embed calls: use `batch_embed` and add exponential backoff / rate-limiting to avoid overloading the embed endpoint.
- Add tests and CI checks: unit tests for `semantic_search.search_by_embedding`, `bytes_to_embedding` edge cases, and `handle_forget_commands` semantics to avoid regressions (tests live under `tests/`).

DONE: (moved from Priority 1)
- Immediate embeddings for critical memories: provide an option to synchronously generate embeddings for high-priority keys (e.g., onboarding fields) so they are searchable immediately. See `src/services/memory_manager.py`.

Example workflows
- User selects a library prompt:
  1. User picks `concise_coach_v1` from UI or via command.
  2. `user_settings.selected_rag_prompt_key` set to `concise_coach_v1`.
  3. On next message with RAG, `PromptRegistry` resolves prompt text and `DialogueEngine` passes it to `PromptBuilder.build_rag_prompt`.

- Admin uploads a template:
  1. Admin creates `template_x` with visibility `public`.
  2. System validates via policy checks; on pass, the template is live.

``` 
