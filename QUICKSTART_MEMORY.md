# Quick Start: Memory & Context System

## 5-Minute Setup

### 1. Initialize Database
```bash
# Run migrations to add conversation tracking columns
alembic upgrade head
```

### 2. Create Test User
```bash
# In Python shell or script
from src.models.database import SessionLocal, User, init_db

init_db()
db = SessionLocal()

user = User(
    external_id="user123",
    channel="telegram",
    first_name="John",
    last_name="Doe",
    opted_in=True
)
db.add(user)
db.commit()
print(f"Created user {user.user_id}")
db.close()
```

### 3. Store User Memories
```bash
# Using curl to call API
curl -X POST "http://localhost:8000/api/v1/dialogue/memory" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "key": "learning_goal",
    "value": "Master Python",
    "category": "goals"
  }'
```

### 4. Send Message with Context
```bash
# Get AI response with full context
curl -X POST "http://localhost:8000/api/v1/dialogue/message" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "text": "Help me with Python functions"
  }'
```

## Python Examples

### Store Multiple Memories
```python
from src.services.memory_manager import MemoryManager
from src.models.database import SessionLocal

db = SessionLocal()
mm = MemoryManager(db)

# Profile
mm.store_memory(1, "full_name", "John Doe", category="profile")

# Goals
mm.store_memory(1, "learning_goal", "Master Python", category="goals", confidence=0.95)

# Preferences
mm.store_memory(1, "preferred_tone", "Friendly and encouraging", category="preferences")

# Temporary conversation state (expires in 24 hours)
mm.store_memory(
    1, 
    "conversation_state", 
    "Discussing Python functions",
    category="conversation",
    ttl_hours=24
)

db.close()
```

### Get User Context
```python
from src.services.prompt_builder import PromptBuilder
from src.services.memory_manager import MemoryManager
from src.models.database import SessionLocal

db = SessionLocal()
mm = MemoryManager(db)
pb = PromptBuilder(db, mm)

# Get all context for a user
context = pb._build_profile_context(user)
print("Profile:", context)

goals = pb._build_goals_context(1)
print("Goals:", goals)

prefs = pb._build_preferences_context(1)
print("Preferences:", prefs)

history = pb._build_conversation_history(1, num_turns=3)
print("Recent history:", history)

db.close()
```

### Process Message with Full Context
```python
from src.services.dialogue_engine import DialogueEngine
from src.models.database import SessionLocal
import asyncio

db = SessionLocal()
engine = DialogueEngine(db)

async def chat():
    response = await engine.process_message(
        user_id=1,
        text="Explain variables to me",
        session=db,
        include_history=True,
        history_turns=4
    )
    print("AI Response:", response)

asyncio.run(chat())
db.close()
```

## API Reference

### POST /api/v1/dialogue/message
```json
{
  "user_id": 1,
  "text": "Your message",
  "include_history": true,
  "history_turns": 4
}
```

### POST /api/v1/dialogue/memory
```json
{
  "user_id": 1,
  "key": "learning_goal",
  "value": "Master Python",
  "category": "goals",
  "confidence": 0.95,
  "ttl_hours": null
}
```

### GET /api/v1/dialogue/memory/{user_id}/{key}
Retrieves memories by key.

### GET /api/v1/dialogue/context/{user_id}
Retrieves complete user context.

### POST /api/v1/dialogue/memory/batch
Store multiple memories at once.

## Common Use Cases

### Onboarding
```python
# Collect user preferences during onboarding
mm.store_memory(user_id, "full_name", name, category="profile")
mm.store_memory(user_id, "learning_goal", goal, category="goals")
mm.store_memory(user_id, "preferred_tone", tone, category="preferences")
```

### Multi-Turn Dialogue
```python
# DialogueEngine automatically includes recent conversation history
# Just call process_message with include_history=True
response = await engine.process_message(
    user_id=1,
    text="User message",
    session=db,
    include_history=True  # Includes recent exchanges
)
```

### Learning Progress Tracking
```python
# Update as user completes lessons
mm.store_memory(
    user_id=1,
    key="lesson_completed",
    value="Python Basics - Variables",
    category="progress"
)
```

### Personalization
```python
# Store insights about learning patterns
mm.store_memory(
    user_id=1,
    key="learning_pattern",
    value="Learns best with code examples",
    category="insights",
    confidence=0.85  # Lower confidence = inferred/uncertain
)
```

## Debugging

### View All Memories for User
```python
from src.models.database import SessionLocal, Memory

db = SessionLocal()
memories = db.query(Memory).filter_by(user_id=1, is_active=True).all()
for m in memories:
    print(f"{m.category}/{m.key}: {m.value} (confidence: {m.confidence})")
db.close()
```

### Check Conversation History
```python
from src.models.database import SessionLocal, MessageLog
from sqlalchemy import desc

db = SessionLocal()
messages = db.query(MessageLog).filter_by(user_id=1).order_by(desc(MessageLog.created_at)).limit(10).all()
for msg in messages:
    print(f"[{msg.direction}] {msg.content[:50]}...")
db.close()
```

### Test Prompt Building
```python
from src.services.prompt_builder import PromptBuilder
from src.services.memory_manager import MemoryManager
from src.models.database import SessionLocal

db = SessionLocal()
mm = MemoryManager(db)
pb = PromptBuilder(db, mm)

# Generate and view prompt
prompt = pb.build_prompt(
    user_id=1,
    user_input="Test message",
    system_prompt="You are helpful"
)
print(prompt)
db.close()
```

## Performance Tips

1. **Batch Operations**: Use `/api/v1/dialogue/memory/batch` for multiple memories
2. **Limit History**: Set `history_turns=2-4` instead of including full history
3. **Archive Old Memories**: Run `memory_manager.purge_expired()` regularly
4. **Index Key Queries**: Ensure database indexes on `user_id`, `key`, `category`

## Next Steps

1. ✅ Run tests: `pytest tests/test_prompt_builder.py -v`
2. ✅ Test API: `curl http://localhost:8000/api/v1/dialogue/context/1`
3. ✅ Review [MEMORY_CONTEXT_SYSTEM.md](MEMORY_CONTEXT_SYSTEM.md) for full documentation
4. ✅ Customize memory categories and keys for your use case
5. ✅ Build onboarding flow to collect initial user context

