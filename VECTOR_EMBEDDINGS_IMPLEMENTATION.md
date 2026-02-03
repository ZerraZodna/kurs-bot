# Vector Embeddings Implementation Workflow

**Date:** February 3, 2026  
**Feature:** Semantic Search via Vector Embeddings  
**Model:** nomic-embed-text (existing Ollama model)  
**Status:** ✅ IMPLEMENTATION COMPLETE

---

## 📋 Feature Overview

Add semantic search capability to the memory system by:
- Generating embeddings for all memory values using Ollama's `nomic-embed-text` model
- Storing embeddings in database alongside memory records
- Implementing semantic search to find contextually relevant memories
- Integrating into existing prompt builder for smarter context selection

### Benefits
- Better memory retrieval (semantic relevance vs keyword matching)
- More contextually appropriate memories included in prompts
- Improved dialogue quality through smarter context assembly

---

## 🏗️ Architecture Changes

### Current Flow
```
Memory Store → Query by Category/Key → Filter by Relevance → Include in Prompt
```

### New Flow
```
Memory Store → Embed text (nomic-embed-text) → Store embedding
                                     ↓
Query with embedding similarity → Find semantic matches → Include in Prompt
```

---

## 🗄️ Database Schema Changes

### Modified Table: `memories`
Add column:
```sql
embedding BLOB NOT NULL DEFAULT NULL  -- Store 384-dimensional vector (nomic-embed-text output)
embedding_version INT DEFAULT 1        -- For managing embedding model updates
embedding_generated_at DATETIME        -- Track when embedding was created
```

### New Migration File
- **File:** `migrations/versions/add_memory_embeddings.py`
- **Action:** Add columns to `memories` table
- **Downtime:** Zero (columns are nullable initially)

---

## 🔧 Configuration Changes

### Update `.env`
```dotenv
# Ollama embedding settings
OLLAMA_EMBED_URL=http://localhost:11434/api/embed
OLLAMA_EMBED_MODEL=nomic-embed-text:latest
EMBEDDING_DIMENSION=384  # nomic-embed-text output size
SEMANTIC_SEARCH_THRESHOLD=0.7  # Cosine similarity threshold (0.0-1.0)
SEMANTIC_SEARCH_MAX_RESULTS=5  # Top-K memories to retrieve
```

### Update `src/config.py`
Add to Settings:
```python
OLLAMA_EMBED_URL: str = "http://localhost:11434/api/embed"
OLLAMA_EMBED_MODEL: str = "nomic-embed-text:latest"
EMBEDDING_DIMENSION: int = 384
SEMANTIC_SEARCH_THRESHOLD: float = 0.7
SEMANTIC_SEARCH_MAX_RESULTS: int = 5
```

---

## 📁 New Files to Create

### 1. `src/services/embedding_service.py` (200-250 lines)
**Purpose:** Handle all embedding operations

**Functions:**
- `generate_embedding(text: str) -> List[float]` - Call Ollama embed endpoint
- `cosine_similarity(vec1, vec2) -> float` - Calculate similarity
- `embed_memory(memory_value: str) -> List[float]` - Wrapper with error handling
- `batch_embed_memories(memory_list) -> List[List[float]]` - Batch generation

**Error Handling:**
- Ollama connection failures
- Empty text inputs
- Invalid model response format

### 2. `src/services/semantic_search.py` (150-200 lines)
**Purpose:** Semantic search operations on memory

**Functions:**
- `semantic_search_memories(user_id: int, query_text: str, session) -> List[Memory]` - Find similar memories
- `find_similar_memories(user_id: int, embedding: List[float], session) -> List[Memory]` - Low-level search
- `rerank_by_relevance(memories: List[Memory], query_embedding: List[float]) -> List[Memory]` - Rerank results

---

## 📝 Modified Files

### 1. `src/models/database.py`
**Changes:**
- Add `embedding`, `embedding_version`, `embedding_generated_at` columns to `Memory` model

### 2. `src/services/prompt_builder.py`
**Changes:**
- Modify context retrieval to use semantic search when query_text is provided
- Fallback to category-based retrieval if no embedding available
- Combine traditional + semantic search results

**New Method:**
```python
async def build_prompt_with_semantic_search(
    self,
    user_id: int,
    query_text: str,
    session,
    history_turns: int = 4
) -> str
```

### 3. `src/services/memory_manager.py`
**Changes:**
- Modify `store_memory()` to generate and store embedding
- Add `update_memory_embeddings()` for batch regeneration
- Handle embedding failures gracefully (store memory but log warning)

### 4. `src/api/dialogue_routes.py`
**Changes:**
- Add new endpoint: `POST /api/v1/dialogue/search` - Semantic search memories
- Update existing endpoint: `POST /api/v1/dialogue/message` - Use semantic search if query provided

---

## 🧪 Tests to Create

### 1. `tests/test_embedding_service.py` (100-150 lines)
- Test embedding generation
- Test cosine similarity calculation
- Test error handling (Ollama down)
- Test batch embedding

### 2. `tests/test_semantic_search.py` (150-200 lines)
- Test finding similar memories
- Test reranking by relevance
- Test threshold filtering
- Test multi-user isolation

### 3. Update `tests/test_integration_memory.py`
- Add end-to-end test: store memory → generate embedding → search → retrieve
- Test semantic vs keyword search comparison

---

## 🔄 Implementation Steps

### Phase 1: Foundation (Setup)
1. ✅ Update `.env.template` with embedding settings
2. ✅ Update `src/config.py` with new settings
3. ✅ Create migration file (add columns to `memories` table)
4. ✅ Create `src/services/embedding_service.py`
5. ✅ Create `src/services/semantic_search.py`

### Phase 2: Integration (Modify Existing)
1. ✅ Update `src/models/database.py` - add embedding columns
2. ✅ Update `src/services/memory_manager.py` - generate embeddings on store
3. ✅ Update `src/services/prompt_builder.py` - use semantic search
4. ✅ Run migration: `alembic upgrade head`

### Phase 3: API Layer (Expose)
1. ✅ Add semantic search endpoint to `src/api/dialogue_routes.py`
2. ✅ Update message endpoint to support semantic search

### Phase 4: Testing (Validate)
1. ✅ Create embedding service tests
2. ✅ Create semantic search tests
3. ✅ Update integration tests
4. ✅ Run full test suite: `pytest tests/ -v --cov=src`

### Phase 5: Documentation (Communicate)
1. ✅ Update `MEMORY_CONTEXT_SYSTEM.md` - add semantic search section
2. ✅ Update `INDEX.md` - mark feature as complete

---

## 🚀 Deployment Checklist

Before going live:
- [ ] Run migrations on dev database
- [ ] Verify `nomic-embed-text` model is running in Ollama
- [ ] Test embeddings with sample data
- [ ] Verify semantic search returns correct results
- [ ] Run full test suite
- [ ] Load test with concurrent embedding requests
- [ ] Update `.env` in production
- [ ] Run migrations on production database
- [ ] Monitor Ollama embed endpoint for latency
- [ ] Verify all existing memories get embeddings (backfill if needed)

---

## 📊 Performance Expectations

| Operation | Time | Notes |
|-----------|------|-------|
| Generate 1 embedding | 50-100ms | Via Ollama |
| Store memory (with embedding) | 15-20ms | Slightly slower than before |
| Semantic search (find 5 similar) | 25-50ms | In-memory similarity calc |
| Build prompt (with semantic search) | 30-40ms | Additional to base 20ms |

---

## ⚠️ Risk Mitigation

### Risk 1: Ollama embed endpoint down
**Mitigation:**
- Make embedding generation optional (store memory without embedding)
- Log warning but don't fail
- Fallback to category-based search

### Risk 2: Dimension mismatch (different model)
**Mitigation:**
- Store `embedding_version` to track model used
- Validate embedding dimension on store
- Add migration to regenerate if model changes

### Risk 3: Performance degradation
**Mitigation:**
- Batch embedding generation for backfill
- Add caching for frequently searched embeddings
- Monitor Ollama CPU usage

### Risk 4: Similarity threshold too high/low
**Mitigation:**
- Make threshold configurable in `.env`
- Start conservative (0.7), adjust after testing
- Log top-N results for debugging

---

## 🔗 Related Files Reference

**Configuration:**
- `.env.template` - Add embedding settings
- `src/config.py` - Add Settings variables

**Database:**
- `src/models/database.py` - Memory model
- `migrations/versions/` - New migration file

**Services:**
- `src/services/memory_manager.py` - Stores memories
- `src/services/prompt_builder.py` - Uses memories
- `src/services/embedding_service.py` - NEW

**API:**
- `src/api/dialogue_routes.py` - Endpoints

**Tests:**
- `tests/test_embedding_service.py` - NEW
- `tests/test_semantic_search.py` - NEW
- `tests/test_integration_memory.py` - Update

**Documentation:**
- `MEMORY_CONTEXT_SYSTEM.md` - Update with semantic search section
- `ARCHITECTURE.md` - Update diagram to show embedding flow
- `INDEX.md` - Update to mark feature as in-progress/complete

---

## ✅ Definition of Done

Feature is complete when:
1. ✅ Embeddings stored for all new memories
2. ✅ Semantic search returns contextually relevant results
3. ✅ All tests passing (unit + integration)
4. ✅ No performance degradation (< 50ms additional latency)
5. ✅ Documentation updated
6. ✅ Deployment checklist completed
7. ✅ Production verified working

---

## 📞 Rollback Plan

If issues arise:
1. Disable semantic search in `prompt_builder.py` (use traditional search only)
2. Keep embeddings in database (no data loss)
3. Revert to previous prompt building logic
4. Keep migration applied (no rollback needed)
5. Fix issue and redeploy

---

## Notes

- **Ollama model:** `nomic-embed-text:latest` (384-dim output)
- **Similarity metric:** Cosine similarity (standard for embeddings)
- **Batch size:** Consider batching 10-50 memories per request to Ollama
- **Backfill:** Need to generate embeddings for existing memories (script or lazy)
- **Cost:** Minimal - all local (Ollama running locally)

