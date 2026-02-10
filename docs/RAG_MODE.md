# RAG Mode — Implementation & Embedding Search

> NOTICE: In this branch persistent memory embeddings and the runtime vector-index feature are disabled. RAG/semantic-search that relies on per-memory embeddings is not active. The notes below describe the previous implementation and how to re-enable vector indexing if needed.

This document summarizes how RAG (Retrieval-Augmented Generation) mode is handled in the codebase, where embeddings were generated and stored historically, and how semantic search over the `memories` table worked.

**Summary**
- RAG mode can be toggled per-message (prefix) or persistently via a stored memory key `rag_mode_enabled`.
- When RAG is active for a message, the dialogue engine performs a semantic search over stored memories and uses a RAG-specific system prompt when building the LLM prompt.
- Embeddings for memories are stored in the `memories.embedding` column (LargeBinary) and are generated asynchronously when memories are created/updated.

- **Where RAG mode is toggled / detected**
- Command handlers (user commands and prefix parsing) live in [src/services/dialogue/command_handlers.py](src/services/dialogue/command_handlers.py#L1-L120): `handle_rag_mode_toggle`, `parse_rag_prefix`, `is_rag_mode_enabled` are the primary functions used to toggle/check RAG mode.
- Note: the toggle accepts the aliases `rag`, `rag mode`, `rag_mode`, and `ragmode` (e.g., `ragmode on`).
- The main request processing flow checks these in `DialogueEngine.process_message` and decides whether to use RAG for the current message: see [src/services/dialogue_engine.py](src/services/dialogue_engine.py#L70-L230).

**Runtime decision points**
- Sequence in `process_message`:
  - `handle_rag_mode_toggle(text, memory_manager, user_id)` — handles explicit commands like `rag_mode on` / `rag_mode off`.
  - `parse_rag_prefix(text)` — supports message-level prefix like `rag: <question>`.
  - `is_rag_mode_enabled(memory_manager, user_id)` — reads persistent `rag_mode_enabled` memory.
  - If RAG is selected for the message, the engine uses `SYSTEM_PROMPT_RAG` and includes semantic search results in the prompt.

**Semantic search service**
- The service is implemented at [src/services/semantic_search.py](src/services/semantic_search.py#L1-L200).
- Public API used by the dialogue engine: `search_memories(user_id, query_text, session, ...)`.
- Implementation details:
  - Generates a query embedding via the embedding service (`generate_embedding`).
  - Historically called an embedding-based search routine which queried `Memory` rows filtering `Memory.embedding IS NOT NULL` and `Memory.is_active == True`. In this branch that routine has been removed and semantic search over per-memory embeddings is disabled.
  - Loads all matching memories (`query.all()`), deserializes stored bytes to vectors with `bytes_to_embedding`, computes cosine similarity in Python, filters by configured threshold, sorts by similarity, and returns the top results (max controlled by config).

**Memory embedding storage & generation**
- `MemoryManager.store_memory(...)` (see [src/services/memory_manager.py](src/services/memory_manager.py#L1-L200)) previously scheduled embedding generation for the stored value. In this branch embedding generation scheduling and per-memory persistence have been removed — embeddings are no longer written to `Memory` rows.

**Embedding service & similarity**
- Implemented at [src/services/embedding_service.py](src/services/embedding_service.py#L1-L200).
- Uses an Ollama embed endpoint configured in settings (`OLLAMA_EMBED_URL` / `OLLAMA_EMBED_MODEL`) to generate embeddings.
- Utilities provided:
  - `generate_embedding(text)` — calls endpoint and validates embedding dimension.
  - `embedding_to_bytes(list[float])` / `bytes_to_embedding(bytes)` — convert to/from binary for DB storage.
  - `cosine_similarity(vec1, vec2)` — computes similarity between vectors (NumPy-based).

**Configuration & thresholds**
- Relevant config values (see [src/config.py](src/config.py#L1-L120)):
  - `OLLAMA_EMBED_URL`, `OLLAMA_EMBED_MODEL`
  - `EMBEDDING_DIMENSION` — embeddings are validated to match this length.
  - `SEMANTIC_SEARCH_THRESHOLD` — similarity cutoff (default 0.4).
  - `SEMANTIC_SEARCH_MAX_RESULTS` — default maximum results returned.
  - `OLLAMA_CHAT_RAG_MODEL` — model used when RAG mode is active for chat.

**Other integrations**
- `handle_forget_commands` (in command handlers) uses `search_memories` to find and archive matching memories by semantic similarity.
  See [src/services/dialogue/command_handlers.py](src/services/dialogue/command_handlers.py#L1-L180).
- Trigger matching/dispatcher also interacts with embeddings (trigger embeddings table and trigger matcher code use the same embedding tools).



**User-facing enable/disable message**
- When RAG is enabled the system now returns a short, informative message to the user explaining what RAG does and how to customize it. Example:

  RAG mode enabled. I will use semantic search over your memories for future messages.

  You can customize RAG behavior:
  - Use `rag_prompt list` to view available prompt templates.
  - Use `rag_prompt select <key>` to pick a template from the library.
  - Use `rag_prompt custom <text>` to set a personal RAG system prompt.

  Tip: prefix a single message with `rag:` to use RAG only for that message.

This message is designed to help users discover prompt customization and per-message usage.
- Embedding dimension mismatches are logged and embeddings rejected — ensure `EMBEDDING_DIMENSION` matches the model output.
- Search uses a fresh SQLAlchemy session (created in `process_message`) to avoid session/lock conflicts.

**Key code locations**
- Dialogue processing / RAG decision: [src/services/dialogue_engine.py](src/services/dialogue_engine.py#L70-L230)
- RAG command & prefix parsing: [src/services/dialogue/command_handlers.py](src/services/dialogue/command_handlers.py#L1-L120)
- Semantic search implementation: [src/services/semantic_search.py](src/services/semantic_search.py#L1-L200)
- Memory model: [src/models/database.py](src/models/database.py#L1-L120)
- Memory manager / embedding generation: [src/services/memory_manager.py](src/services/memory_manager.py#L1-L200)
- Embedding service (Ollama): [src/services/embedding_service.py](src/services/embedding_service.py#L1-L200)
- Config and defaults: [src/config.py](src/config.py#L1-L120)


(Report generated from code inspection on repository.)
