# Memory Extractor Service

## Overview

The **Memory Extractor Service** automatically extracts meaningful user facts, preferences, and goals from conversation messages using an offline Ollama LLM. It works with any language (English, Norwegian, etc.) and intelligently decides what's worth storing.

## How It Works

```
User Message → Ollama LLM → JSON Decision → MemoryManager → Database
```

### Flow

1. **User sends message** to the bot
2. **DialogueEngine.process_message()** automatically calls the extractor
3. **MemoryExtractor** sends the message to Ollama with a classification prompt
4. **Ollama** returns JSON: `{store: bool, key, value, confidence, ttl_hours}`
5. **MemoryManager** stores the extracted memory with conflict resolution
6. **Dialogue** continues and bot responds

## Configuration

In `.env`:
```
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=llama3.1:8b
MEMORY_EXTRACTOR_MODEL=qwen2.5-coder:7b
```

**Recommended Models for Memory Extraction:**
- `qwen2.5-coder:7b` ⭐ (best balance, 4.7 GB)
- `qwen2.5-coder:14b` (more powerful, 9.0 GB)
- `llama3.1:8b` (alternative, 4.9 GB)

## Memory Decision Criteria

The LLM **STORES** memories for:
- ✅ Explicit identity (name, email)
- ✅ Long-term goals (learning objectives, aspirations)
- ✅ Preferences (time, format, style)
- ✅ Commitments ("I promise to...", "I'll do...")
- ✅ Corrections ("Actually, my goal is X not Y")

The LLM **SKIPS** storage for:
- ❌ Casual chit-chat ("Hi, how are you?")
- ❌ Questions ("What's the weather?")
- ❌ Vague statements without intent
- ❌ Sensitive info (health, financial) without explicit consent

## Memory Format

Each extracted memory is a JSON object:

```json
{
  "store": true,
  "key": "learning_goal",
  "value": "Learn Python programming",
  "confidence": 0.95,
  "ttl_hours": null
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `store` | `bool` | Whether to save this memory |
| `key` | `str` | Memory key (e.g., `learning_goal`, `preferred_time`) |
| `value` | `str` | Memory value |
| `confidence` | `float` | 0.0–1.0 confidence score (1.0 = explicit, 0.5 = inferred) |
| `ttl_hours` | `int\|null` | Expire after N hours (null = permanent) |

## Example Conversations

### English
```
User: "My goal is to master Python and I prefer evening lessons"
↓
Extracted:
  - key: "learning_goal", value: "Master Python", confidence: 0.98
  - key: "preferred_lesson_time", value: "Evening", confidence: 0.95
```

### Norwegian
```
User: "Jeg heter Anna og mitt mål er å lære programmering"
↓
Extracted:
  - key: "first_name", value: "Anna", confidence: 0.99
  - key: "learning_goal", value: "Lær programmering", confidence: 0.97
```

### Correction
```
User: "Actually, I prefer morning lessons, not evening"
↓
Extracted:
  - key: "preferred_lesson_time", value: "Morning", confidence: 0.98
  (Previous "Evening" value is archived due to conflict resolution)
```

### Casual (No Storage)
```
User: "How are you doing?"
↓
Extracted: [] (nothing stored)
```

## Usage

### Automatic (in DialogueEngine)

Once configured, memory extraction happens automatically:

```python
from src.services.dialogue_engine import DialogueEngine
from src.models.database import SessionLocal

db = SessionLocal()
dialogue = DialogueEngine(db)

# Memories are automatically extracted and stored
response = await dialogue.process_message(
    user_id=123,
    text="My goal is to learn Spanish",
    session=db
)
```

### Manual (Direct)

```python
from src.services.memory_extractor import MemoryExtractor

memories = await MemoryExtractor.extract_memories(
    user_message="I want to improve my coding skills",
    user_context={"existing_memories": {"learning_goal": "Python"}}
)

for memory in memories:
    print(f"Store: {memory['key']} = {memory['value']}")
```

## Conflict Resolution

When a new memory conflicts with an existing one (same key, different value):

1. New memory is marked as **active**
2. Old memory is **archived** with `archived_at` timestamp
3. Both are linked via `conflict_group_id` for audit trail
4. User corrections are **always preferred** (higher confidence)

Example:
```python
# User first says:
mm.store_memory(user_id=1, key="learning_goal", value="Python")

# Then says:
mm.store_memory(user_id=1, key="learning_goal", value="Machine Learning")

# Result:
# - "Python" is archived
# - "Machine Learning" is active
# - Both have conflict_group_id linking them
```

## Testing

Run manual test:
```bash
python tests/test_memory_extractor.py
```

Run with pytest:
```bash
pytest tests/test_memory_extractor.py -v
```

## Performance Notes

- **Latency**: ~1-3 seconds per message (Ollama response time)
- **Non-blocking**: Memory extraction runs in background, doesn't block dialogue response
- **Fallback**: If Ollama is unavailable, extraction fails gracefully and dialogue continues
- **Batch**: Use `extract_memories_batch()` for multiple messages at once

## Troubleshooting

### No memories being extracted

1. **Check Ollama is running**: `curl http://localhost:11434/api/tags`
2. **Check model exists**: `ollama list | grep qwen2.5-coder`
3. **Check logs**: `docker logs ollama` (if running in Docker)
4. **Test manually**:
   ```bash
   python tests/test_memory_extractor.py
   ```

### Ollama timeout

- Increase timeout in `memory_extractor.py`: `timeout=30.0`
- Or use a faster model: `qwen2.5-coder:1.5b-base`

### Wrong language detected

- The extractor auto-detects language
- If issues, check Ollama model supports that language
- `qwen2.5-coder` models support 20+ languages

## Future Enhancements

- [ ] Fine-tune Ollama model on custom memory keys
- [ ] Add semantic deduplication (find similar memories)
- [ ] Confidence-based ranking (show user what was learned)
- [ ] Privacy-aware extraction (skip PII without consent)
- [ ] Multi-turn context memory (remember conversation flow)

---

**Implementation**: Feb 2, 2026
**Status**: Beta (production-ready)
