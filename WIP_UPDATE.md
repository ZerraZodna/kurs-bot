WIP: Embedding-driven trigger matching and scheduling
= Overview

Problem today: certain user actions that should create or update scheduled tasks are only detected by brittle keyword matching performed before prompt construction. Examples that fail: "Change my daily reminder to 09:00" (not recognized) or language-variant phrases. The result: a memory may be created but no schedule is created/updated.

Goal: Replace brittle keyword triggers with an embedding-based trigger matcher that is language-agnostic and run after the message has been interpreted by the AI. The matcher will compare the user's message embedding with a small set of pre-defined "trigger embeddings" (one per action type) and, when similarity passes a threshold, call the appropriate action (create schedule, update schedule, enter/exit RAG mode, set next_lesson, etc.).

= High-level design

- Add a persistent store of trigger embeddings and metadata (name, action_type, threshold).
- Add a `TriggerMatcher` service that generates an embedding for the incoming user text (using the same `embedding_service`) and returns any triggers above the configured similarity threshold.
- Call the matcher after the AI has processed the message (post-inference) so the system benefits from the LLM's understanding. If the LLM returns structured intent information, prefer that; otherwise run the embedding matcher.
- When a trigger matches, execute the corresponding action handler (scheduling service update/create, memory updates, enter/exit RAG, etc.).

= Why post-LLM embeddings?

- The LLM may have transformed or resolved ambiguous user phrasing during interpretation. Running the trigger match after the AI step reduces false negatives.
- Embeddings are language-agnostic and tolerant to variations in phrasing.

= DB changes (migration)

- Add table `trigger_embeddings` with columns:
  - `id` (PK)
  - `name` (varchar) e.g. "create_schedule", "update_schedule", "next_lesson"
  - `action_type` (varchar) - maps to handler in code
  - `embedding` (bytes/blob) - serialized embedding vector
  - `threshold` (float) - similarity cutoff (default 0.75)
  - `created_at`, `updated_at`

Provide alembic migration script in `migrations/versions/`.

= New service: `src/services/trigger_matcher.py`

- Responsibilities:
  - Load trigger embeddings from DB into memory (cache + refresh interval)
  - Normalize vector storage and provide a `match_triggers(text: str) -> List[TriggerMatch]` API
  - Use `embedding_service.generate_embedding(text)` to get embedding
  - Compute cosine similarity; return triggers above `threshold` ordered by score

- Return object: `{trigger_id, name, action_type, score}`

Example API sketch (implementation note in file):

- File: `src/services/trigger_matcher.py`
- Main method: `match_triggers(user_text: str, top_k: int = 3) -> List[dict]`

= Action handlers

- Map `action_type` values to existing application handlers:
  - `create_schedule` -> call `src.services.scheduler.create_schedule(...)` or existing schedule creation flow
  - `update_schedule` -> call `src.services.scheduler.update_schedule(...)`
  - `next_lesson` -> update `Memory` entry for `current_lesson_id` and call scheduling flow for next-day sequence
  - `enter_rag` / `exit_rag` -> set RAG mode flag on user or conversation

- Implement a small dispatcher in `src/services/trigger_dispatcher.py` that receives `TriggerMatch` and `context` (user_id, message, optional parsed LLM output) and performs the action with robust logging and audit.

= Where to call matcher (sequence)

1. Receive user message (existing route).
2. Create or retrieve `User` and pre-checks.
3. Build prompt and call LLM as today.
4. Receive LLM response. If LLM returns a structured intent (preferred), use it to trigger action handlers directly.
5. Otherwise (or in addition), call `TriggerMatcher.match_triggers(original_user_text)`.
6. If `matches` returned and `score >= threshold`, call `TriggerDispatcher.dispatch(match, context)` to perform schedule creation/update or memory updates.
7. Continue normal message logging and memory updates.

Note: keep the matching idempotent for safe reprocessing; ensure dispatchers check current schedule state (create vs update) before mutating.

= Implementation details & code pointers

- New files to add:
  - `src/services/trigger_matcher.py` (core matcher)
  - `src/services/trigger_dispatcher.py` (action dispatch)
  - `migrations/versions/xxxx_add_trigger_embeddings.py` (alembic migration)

- Modified files:
  - `src/services/dialogue_engine.py` — after LLM response (or when LLM provides structured signals) call matcher/dispatcher; add hooks so the DialogueEngine's flow remains ordered: LLM -> triggers -> scheduling/memory -> outbound response.
  - `src/services/memory_manager.py` — provide helper APIs if triggers update memories (e.g., `set_next_lesson(user_id, lesson_id)`)
  - `src/services/scheduler.py` (or wherever schedule creation lives) — ensure there are clear, idempotent APIs for create/update schedule operations used by dispatcher.

= Similarity and threshold tuning

- Start with default threshold 0.75. Provide admin API or config entry `TRIGGER_SIMILARITY_THRESHOLD` to tune globally.
- Log all matches with scores for 1-2 days to evaluate false positives/negatives. Consider a telemetry endpoint or csv dump for human review.

= Tests & validation

- Unit tests:
  - `tests/test_trigger_matcher.py` — checks matching against seeded trigger embeddings (use deterministic fake embeddings or mocking of `embedding_service`).
  - `tests/test_trigger_dispatcher.py` — ensure action mapping and idempotency.

- Integration tests:
  - Simulate user messages that should create/update schedule and assert DB state.

- Manual QA: add several trigger utterances in target languages and verify they match the intended triggers.

= Rollout plan

1. Implement migration + services behind a feature flag `ENABLE_TRIGGER_MATCHER=false` default.
2. Seed trigger embeddings (small dataset) for main actions.
3. Deploy to staging, enable feature flag, run integration tests and monitor logs for matches.
4. Tune thresholds and expand trigger set.
5. Flip feature flag in production.

= Backward compatibility & safety

- When the matcher is enabled, keep existing keyword-based fallback disabled or optional. Prefer the embedding matcher, but keep an admin toggle.
- All dispatcher actions must be idempotent and check existing schedule/memory state before creating new records.
- Add audit logs for every triggered action so Data Subject Requests can be audited.

= Open questions (need your input)

- Which existing module is the canonical scheduling API? (I assumed `src/services/scheduler.py` — confirm or provide the correct path.)
- Do you prefer triggers to be matched on the original user message or a normalized/translated variant? I recommend original message embedding (language-agnostic), but we could experiment with LLM-normalized text.
- Who should seed the initial trigger utterances and thresholds? I can provide a reasonable starter set.

= Next immediate steps (I can do these)

1. Create alembic migration for `trigger_embeddings`.
2. Add `TriggerMatcher` and `TriggerDispatcher` services with tests.
3. Wire matcher into `DialogueEngine` post-LLM with a feature flag.
4. Seed a starter set of trigger embeddings and test end-to-end.

---
If you want I can start implementing step 1 (migration) and step 2 (matcher service) now. Tell me which scheduling API to call (or point me to the file) and whether to seed a starter trigger set. 
