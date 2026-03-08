# User Memory & Context Prompt Building System

## Overview

This system provides intelligent, multi-user context-aware prompt building for your Ollama-based AI backend. It maintains user-specific memories, conversation history, and preferences to generate personalized prompts that improve response quality and continuity.

## Architecture

### Components

```
┌─────────────────────────────────────────┐
│         FastAPI Application             │
│  (src/api/app.py + dialogue_routes.py)  │
└────────────┬────────────────────────────┘
             │
     ┌───────┴────────┐
     ▼                ▼
┌──────────┐     ┌────────────────────┐
│DialogueE │     │ PromptBuilder      │
│ngine     │────▶│ (context assembly) │
└──────────┘     └──────┬─────────────┘
                        │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
        ┌────────┐ ┌──────────┐ ┌──────────┐
        │Memory  │ │Message   │ │User      │
        │Manager │ │Log       │ │Profile   │
        └────────┘ └──────────┘ └──────────┘
            │           │           │
            └───────────┴───────────┘
                   ▼
            ┌─────────────────┐
            │   SQLAlchemy    │
            │   Database      │
            └─────────────────┘
```

### Key Services

#### 1. **MemoryManager** (`src/services/memory_manager.py`)
- Stores and retrieves user memories
- Implements conflict resolution for contradictory memories
- Supports TTL (time-to-live) for temporary context
- Organizes memories by category and key

#### 2. **PromptBuilder** (`src/services/prompt_builder.py`)
- Assembles context-aware prompts dynamically
- Queries relevant memories by category and recency
- Formats conversation history for multi-turn dialogue
- Optimizes token usage
- Returns formatted prompts ready for Ollama

#### 3. **DialogueEngine** (`src/services/dialogue_engine.py`)
- Orchestrates memory + prompt building
- Calls Ollama with context-aware prompts
- Logs conversations for history tracking
- Handles multi-turn dialogue state

#### 4. **Context Utilities** (`src/services/context_utils.py`)
- Standard memory categories and keys
- Token estimation and optimization
- Conversation formatting helpers
- Prompt templates for common scenarios

## Memory System

### Categories

Memories are organized into six categories:

| Category | Purpose | Examples |
|----------|---------|----------|
| `profile` | User demographics and info | Name, timezone, language, accessibility |
| `goals` | Learning objectives | Learning goals, milestones, completion rate |
| `preferences` | Communication style | Tone, frequency, difficulty level |
| `progress` | Learning achievements | Lessons completed, practice streaks |
| `insights` | AI-derived understanding | Learning patterns, strengths, gaps |
| `conversation` | Active context | Last topic, open questions, state |

### Memory Keys

Standard keys for consistent access:

```python
from src.services.context_utils import MemoryKey

# Profile
MemoryKey.FULL_NAME
MemoryKey.LANGUAGE

# Preferences
MemoryKey.PREFERRED_TONE
```

## API Endpoints

### Dialogue

#### `POST /api/v1/dialogue/message`
Send a message and get AI response with full context.

```json
{
  "user_id": 1,
  "text": "Help me understand the concept",
  "include_history": true,
  "history_turns": 4
}
```

Response:
```json
{
  "user_id": 1,
  "response": "Based on your learning goals...",
  "model": "ollama"
}
```

#### `POST /api/v1/dialogue/onboard`
Get onboarding prompt for new users.

```json
{
  "user_id": 2
}
```

### Memory Management

#### `POST /api/v1/dialogue/memory`
Store a memory for a user.

```json
{
  "user_id": 1,
  "key": "learning_goal",
  "value": "Master Python programming",
  "category": "goals",
  "confidence": 0.95,
  "ttl_hours": null
}
```

#### `GET /api/v1/dialogue/memory/{user_id}/{key}`
Retrieve memories by key.

```
GET /api/v1/dialogue/memory/1/learning_goal
```

Response:
```json
{
  "user_id": 1,
  "key": "learning_goal",
  "memories": [
    {
      "memory_id": 42,
      "key": "learning_goal",
      "value": "Master Python programming",
      "confidence": 0.95,
      "source": "dialogue_engine",
      "created_at": "2026-02-02T10:00:00Z"
    }
  ]
}
```

#### `GET /api/v1/dialogue/context/{user_id}`
Get complete user context.

```
GET /api/v1/dialogue/context/1
```

Response:
```json
{
  "user_id": 1,
  "name": "John Doe",
  "goals": [
    {"value": "Master Python programming", "confidence": 0.95}
  ],
  "preferences": [
    {"value": "Professional tone", "confidence": 1.0}
  ],
  "recent_progress": [
    {"value": "Completed Lesson 1", "confidence": 1.0}
  ]
}
```

#### `POST /api/v1/dialogue/memory/batch`
Store multiple memories in one request.

```json
{
  "requests": [
    {
      "user_id": 1,
      "key": "full_name",
      "value": "John Doe",
      "category": "profile"
    },
    {
      "user_id": 1,
      "key": "learning_goal",
      "value": "Master Python",
      "category": "goals"
    }
  ]
}
```

## Usage Examples

### Basic Dialogue with Context

```python
from sqlalchemy.orm import Session
from src.services.dialogue_engine import DialogueEngine
from src.models.database import SessionLocal

db = SessionLocal()
dialogue_engine = DialogueEngine(db)

# Process message with full context awareness
response = await dialogue_engine.process_message(
    user_id=1,
    text="Explain recursion to me",
    session=db,
    include_history=True,
    history_turns=4,
)

print(response)
```

### Storing User Goals

```python
from src.memories import MemoryManager
from src.services.context_utils import MemoryKey, MemoryCategory

memory_manager = MemoryManager(db)

# Store learning goal
memory_manager.store_memory(
    user_id=1,
    key=MemoryKey.LEARNING_GOAL,
    value="Master Python programming",
    category=MemoryCategory.GOALS,
    confidence=0.95,
)

# Store preference
memory_manager.store_memory(
    user_id=1,
    key=MemoryKey.PREFERRED_TONE,
    value="Friendly and encouraging",
    category=MemoryCategory.PREFERENCES,
)
```

### Building Custom Prompts

```python
from src.language.prompt_builder import PromptBuilder

prompt_builder = PromptBuilder(db, memory_manager)

# Build context-aware prompt
prompt = prompt_builder.build_prompt(
    user_id=1,
    user_input="What should I practice next?",
    system_prompt="You are a helpful Python tutor.",
    include_conversation_history=True,
    history_turns=4,
)

# Use with Ollama
response = await dialogue_engine.call_ollama(prompt)
```

### Retrieving User Context

```python
from src.services.context_utils import MemoryKey

# Get user's learning goals
goals = memory_manager.get_memory(user_id=1, key=MemoryKey.LEARNING_GOAL)
for goal in goals:
    print(f"Goal: {goal['value']}")
    print(f"Confidence: {goal['confidence']:.0%}")
```

## Prompt Structure

The final prompt follows this structure:

```
[SYSTEM PROMPT - Persona/Role]

### User Profile
Name: John Doe
Email: john@example.com
Channel: telegram
User since: 30 days ago

### Current Goals
Learning Goals:
  1. Master Python programming (confidence: 95%)
  2. Build web applications

### Preferences
Learning Style: Hands-on with examples
Preferred Tone: Friendly and encouraging

### Recent Progress
Recent Lessons:
  1. Python Basics
  2. Data Types and Variables
Recent Insights:
  1. User learns best with practical examples

### Recent Conversation
User: What's a list comprehension?
Assistant: A list comprehension is a concise way to create lists...
User: Can I use it with nested loops?
Assistant: Yes! You can nest comprehensions...

### Current Message
User: How do I filter a list?
Assistant:
```

## Database Schema

### New/Updated Models

```python
# Enhanced MessageLog with conversation tracking
class MessageLog(Base):
    message_id: int          # Primary key
    user_id: int             # Foreign key to users
    direction: str           # inbound|outbound
    channel: str             # telegram|email|slack|dialogue_engine
    content: Text            # Message content
    status: str              # queued|sent|delivered|failed
    message_role: str        # user|assistant (for LLM context)
    conversation_thread_id: str  # Groups related messages
    created_at: DateTime     # Timestamp
    processed_at: DateTime   # When processed

# Existing Memory model (unchanged)
class Memory(Base):
    memory_id: int
    user_id: int
    category: str            # profile|goals|preferences|progress|insights|conversation
    key: str                 # Specific memory key
    value: Text              # JSON-friendly value
    value_hash: str          # For conflict detection
    confidence: float        # 0.0 to 1.0
    is_active: bool          # Soft delete
    created_at: DateTime
    updated_at: DateTime
    ttl_expires_at: DateTime  # Optional expiration
```

## Testing

Run tests with pytest:

```bash
pytest tests/test_prompt_builder.py -v
```

Test coverage includes:

- ✅ Basic prompt building
- ✅ Profile context inclusion
- ✅ Goals and preferences integration
- ✅ Conversation history tracking
- ✅ Memory conflict resolution
- ✅ TTL (time-to-live) expiration
- ✅ Token optimization
- ✅ Batch operations

## Configuration

### Environment Variables

```env
DATABASE_URL=sqlite:///./src/data/dev.db
OLLAMA_MODEL=llama3.1:8b
SYSTEM_PROMPT="You are a spiritual coach specializing in A Course in Miracles..."
```

### Token Limits

Customize in `PromptBuilder.TOKEN_LIMITS`:

```python
TOKEN_LIMITS = {
    "profile": 150,
    "goals": 200,
    "preferences": 100,
    "progress": 150,
    "conversation_history": 400,
}
```

## Best Practices

### 1. Memory Storage
- **Be specific**: Use clear, unambiguous values
- **Set confidence**: Lower confidence for uncertain facts (0.7-0.9)
- **Use TTL**: Set expiration for temporary context
- **Categorize properly**: Use appropriate categories for consistent retrieval

### 2. Prompt Building
- **Balance context**: Include relevant memories without overwhelming the model
- **Respect limits**: Keep total prompt under model's token limit
- **Order matters**: Profile → Goals → Preferences → History → Current message
- **Test variations**: Experiment with history_turns and include_history flags

### 3. Conversation Tracking
- **Log consistently**: Always log both user and assistant messages
- **Group threads**: Use conversation_thread_id for related exchanges
- **Set message_role**: Distinguish between 'user' and 'assistant' roles
- **Clean up**: Periodically purge old messages

### 4. Multi-User Safety
- Always filter memories by user_id
- Validate user exists before processing
- Use database transactions for consistency
- Log errors for debugging

## Performance Optimization

### Token Estimation
```python
from src.services.context_utils import ContextOptimizer

tokens = ContextOptimizer.estimate_tokens("Your text here")
truncated = ContextOptimizer.truncate_by_tokens(text, max_tokens=500)
```

### Memory Retrieval
- Query only active memories (`is_active=True`)
- Filter by category for faster lookups
- Use `limit()` to cap results
- Purge expired entries regularly

### Conversation History
- Store message_role for efficient filtering
- Use conversation_thread_id for batching
- Limit history_turns to 4-8 for cost efficiency
- Summarize long conversations when needed

## Troubleshooting

### Prompts Too Long
1. Reduce `history_turns` (default 4)
2. Increase token limit in `build_prompt()`
3. Summarize conversation history

### Missing Context
1. Verify memory is stored with `get_memory()`
2. Check category and key match expected values
3. Ensure memory is active (`is_active=True`)
4. Check TTL expiration if applicable

### Database Errors
1. Run migrations: `alembic upgrade head`
2. Check SQLAlchemy session handling
3. Verify user exists before processing
4. Use transaction rollback on errors

## Future Enhancements

- [ ] Vector embeddings for semantic memory search
- [ ] Memory summarization for long histories
- [ ] Automatic insight generation
- [ ] User preference learning
- [ ] Multi-language support
- [ ] Memory versioning and audit logs
- [ ] A/B testing for prompt variations
- [ ] Real-time memory updates during conversation

## References

- [PromptBuilder](src/services/prompt_builder.py) - Core context assembly
- [MemoryManager](src/services/memory_manager.py) - Memory operations
- [DialogueEngine](src/services/dialogue_engine.py) - Orchestration
- [Context Utils](src/services/context_utils.py) - Utilities and constants
- [API Routes](src/api/dialogue_routes.py) - REST endpoints
- [Tests](tests/test_prompt_builder.py) - Usage examples
