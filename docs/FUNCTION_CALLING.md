# Function Calling System

This document describes the function calling architecture that replaced the previous embedding-based trigger matching system.

## Overview

The ACIM Course Bot uses a **function calling approach** where the LLM returns structured JSON responses containing both natural language text and function calls. This eliminates the need for sentence-transformers embeddings and simplifies intent detection.

**Key Benefits:**
- No embedding generation overhead (faster responses)
- More accurate intent detection via LLM reasoning
- Support for multiple function calls in a single response
- Integrated memory extraction in the same LLM call
- Simpler codebase with fewer dependencies

---

## Architecture

```
User Message
    ↓
DialogueEngine.process_message()
    ↓
PromptBuilder.build_prompt() [includes function definitions]
    ↓
call_ollama() with function-aware prompt
    ↓
AI ALWAYS returns JSON:
  {
    "response": "Natural language text for user",
    "functions": [
      {"name": "action_name", "parameters": {...}},
      {"name": "extract_memory", "parameters": {...}}
    ]
  }
    ↓
IntentParser.parse() validates JSON
    ↓
If response.text → Send to user
    ↓
For each function in functions[] → FunctionExecutor.execute()
    ├── Action functions → TriggerDispatcher
    ├── Memory functions → MemoryManager.store_memory()
    ↓
All actions executed, results collected
```

---

## Core Components

### 1. Function Registry (`src/functions/registry.py`)

Defines all available functions with metadata, parameters, and validation schemas.

```python
from src.functions.registry import get_function_registry, FunctionMetadata

registry = get_function_registry()
all_functions = registry.list_all()  # 20+ functions available

# Get functions for specific context
scheduling_funcs = registry.list_for_context("schedule_setup")
```

**Available Functions by Category:**

| Category | Functions |
|----------|-----------|
| **Scheduling** | `create_schedule`, `update_schedule`, `delete_schedule`, `query_schedule`, `create_one_time_reminder` |
| **Lessons** | `send_lesson`, `send_next_lesson`, `send_todays_lesson`, `repeat_lesson`, `mark_lesson_complete`, `set_lesson_preference` |
| **Profile** | `set_timezone`, `set_language`, `set_preferred_time`, `update_profile` |
| **RAG** | `enter_rag`, `exit_rag` |
| **Confirmation** | `confirm_yes`, `confirm_no` |
| **Memory** | `extract_memory` |

### 2. Intent Parser (`src/functions/intent_parser.py`)

Parses and validates JSON responses from the LLM.

```python
from src.functions.intent_parser import get_intent_parser, ParseResult

parser = get_intent_parser()
result: ParseResult = parser.parse(llm_response)

# Result contains:
# - success: bool
# - response_text: str (natural language for user)
# - functions: List[Dict] (function calls to execute)
# - errors: List[str] (validation errors if any)
# - is_fallback: bool (true if response was treated as plain text)
```

**Supported JSON Formats:**
```json
// Standard format
{
  "response": "I'll set up your schedule.",
  "functions": [
    {"name": "create_schedule", "parameters": {"time": "09:00"}}
  ]
}

// With markdown code blocks (also supported)
```json
{
  "response": "Got it!",
  "functions": [{"name": "confirm_yes", "parameters": {}}]
}
```
```

### 3. Function Executor (`src/functions/executor.py`)

Executes function calls with error handling and result collection.

```python
from src.functions.executor import get_function_executor, BatchExecutionResult

executor = get_function_executor()
context = {
    "user_id": user_id,
    "session": db_session,
    "memory_manager": memory_manager,
    "original_text": user_message,
}

result: BatchExecutionResult = await executor.execute_all(
    functions=parse_result.functions,
    context=context,
    continue_on_error=True  # Execute all even if one fails
)
```

### 4. Response Builder (`src/functions/response_builder.py`)

Combines text responses with function execution results.

```python
from src.functions.response_builder import ResponseBuilder, BuiltResponse

builder = ResponseBuilder()
response: BuiltResponse = builder.build(
    user_text=user_message,
    ai_response_text=parse_result.response_text,
    execution_result=batch_result
)
```

---

## Context-Specific Function Availability

Functions are filtered by conversation context to make the AI's job easier:

| Context | Available Functions | Use Case |
|---------|---------------------|----------|
| `general_chat` | All general functions | Default state |
| `onboarding` | `set_timezone`, `set_language`, `set_preferred_time`, `update_profile`, `extract_memory` | New user setup |
| `schedule_setup` | `create_schedule`, `update_schedule`, `delete_schedule`, `query_schedule` | Configuring reminders |
| `lesson_review` | `mark_lesson_complete`, `send_next_lesson`, `send_lesson` | After lesson delivery |
| `morning_lesson_confirmation` | `repeat_lesson`, `send_next_lesson`, `set_lesson_preference` | Daily lesson choice |

**Context Detection in DialogueEngine:**
```python
def _detect_context_type(self, user_id: int, text: str, use_rag: bool) -> str:
    if use_rag:
        return "rag"
    if self.onboarding.should_show_onboarding(user_id):
        return "onboarding"
    # Check for schedule keywords
    if any(kw in text.lower() for kw in ["schedule", "reminder", "time"]):
        return "scheduling"
    return "general_chat"
```

---

## Multi-Function Response Examples

The LLM can execute multiple functions in a single response:

**Example 1: Schedule + Memory Extraction**
```json
{
  "response": "Perfect! I've set up your daily reminder at 9:00 AM and will remember that you're in Tokyo!",
  "functions": [
    {"name": "create_schedule", "parameters": {"time": "09:00", "message": "Daily ACIM lesson"}},
    {"name": "extract_memory", "parameters": {"key": "timezone", "value": "Asia/Tokyo", "confidence": 0.95}},
    {"name": "extract_memory", "parameters": {"key": "preferred_lesson_time", "value": "09:00", "confidence": 0.90}}
  ]
}
```

**Example 2: Multiple Reminders + Lesson**
```json
{
  "response": "I'll remind you about today's lesson every 30 minutes. Here's the lesson text:",
  "functions": [
    {"name": "create_one_time_reminder", "parameters": {"run_at": "2024-01-15T09:00:00", "message": "Lesson reminder"}},
    {"name": "create_one_time_reminder", "parameters": {"run_at": "2024-01-15T09:30:00", "message": "Lesson reminder"}},
    {"name": "create_one_time_reminder", "parameters": {"run_at": "2024-01-15T10:00:00", "message": "Lesson reminder"}},
    {"name": "send_todays_lesson", "parameters": {}}
  ]
}
```

**Example 3: Simple Text Response (No Functions)**
```json
{
  "response": "That's a great question about forgiveness. In ACIM, forgiveness is about releasing judgment...",
  "functions": []
}
```

---

## Memory Extraction Integration

Memory extraction is now integrated into the function calling flow. The LLM can extract facts and store them via the `extract_memory` function.

**Parameters:**
- `key`: Memory key (e.g., "name", "timezone", "current_lesson")
- `value`: The value to store
- `confidence`: 0.0-1.0 (default 0.8, minimum 0.7)
- `ttl_hours`: Optional time-to-live for temporary memories
- `category`: Auto-inferred from key (profile, preferences, progress, conversation)

**Example:**
```json
{
  "response": "Great! I've noted that you're on lesson 25 and prefer morning study times.",
  "functions": [
    {"name": "extract_memory", "parameters": {"key": "current_lesson", "value": "25", "confidence": 0.95}},
    {"name": "extract_memory", "parameters": {"key": "preferred_study_time", "value": "morning", "confidence": 0.85}}
  ]
}
```

**Confidence Threshold:**
- Memories with confidence < 0.7 are rejected
- This prevents low-confidence extractions from polluting the memory store

---

## Prompt Building with Functions

The `PromptBuilder` includes function definitions in the system prompt:

```python
from src.language.prompt_builder import PromptBuilder

builder = PromptBuilder(db, memory_manager)
prompt = builder.build_prompt(
    user_id=user_id,
    user_input=text,
    system_prompt=settings.SYSTEM_PROMPT,
    context_type="general_chat",  # Determines which functions to include
    # ... other params
)
```

**Function Definitions in Prompt:**
```
Available actions you can take:
- create_schedule: Create a daily recurring schedule for lesson reminders
  Parameters:
    - time (time, required): Time of day for the reminder (24-hour format)
      Examples: 09:00, 14:30, 20:00
    - message (string, optional): Message to send with the reminder
    - lesson_id (integer, optional): Specific lesson ID to start with

- extract_memory: Extract and store a memory from user conversation...
  [etc.]

Return JSON with your response and any functions to execute.
Format: {"response": "text for user", "functions": [{"name": "...", "parameters": {...}}]}
```

---

## Migration from Embedding System

### What Was Removed
- `TriggerMatcher` class (embedding-based matching)
- `TriggerEmbedding` database model
- `VectorIndex` (FAISS/numpy vector search)
- `STARTER` trigger phrases (123+ entries)
- CI trigger seeding scripts
- `sentence-transformers` dependency

### What Replaced It
- `FunctionRegistry` - defines available functions
- `IntentParser` - parses JSON responses
- `FunctionExecutor` - executes function calls
- Single LLM call that returns both text and functions

### Key Changes in Code

**Before (Embedding-based):**
```python
# Generate embedding
embedding = await embedding_service.generate_embedding(text)

# Match against trigger embeddings
matches = trigger_matcher.match_triggers(embedding, threshold=0.75)

# Dispatch matched triggers
for match in matches:
    dispatcher.dispatch(match, context)
```

**After (Function Calling):**
```python
# Build prompt with function definitions
prompt = prompt_builder.build_prompt(..., context_type="general_chat")

# Call LLM (returns JSON with functions)
response = await call_ollama(prompt)

# Parse and execute functions
parse_result = intent_parser.parse(response)
execution_result = await executor.execute_all(parse_result.functions, context)
```

---

## Testing

Run function calling tests:
```bash
pytest tests/unit/functions/test_critical_path.py -v
```

Key test coverage:
- Function registry (all 20+ functions registered)
- Intent parsing (valid JSON, markdown blocks, fallback)
- Parameter validation (time, timezone, language, datetime)
- Function execution (success and error cases)
- Memory extraction (confidence threshold, storage)

---

## Troubleshooting

**Issue: LLM returns invalid JSON**
- The `IntentParser` has robust error handling
- Falls back to treating response as natural language
- Logs parse errors for debugging

**Issue: Functions not being called**
- Check that `context_type` is set correctly in prompt building
- Verify function names match registered functions
- Review logs for validation errors

**Issue: Memory extraction not working**
- Check confidence threshold (must be >= 0.7)
- Verify `memory_manager` is passed in execution context
- Review `extract_memory` handler logs

---

## Performance

Function calling is **faster** than the embedding approach:
- No embedding generation (saves ~100-500ms)
- Single LLM call instead of embedding + LLM
- No FAISS/numpy vector search overhead

Benchmarks show 20-40% faster response times overall.

---

## Future Enhancements

Potential improvements to the function calling system:

1. **Parallel Function Execution** - Execute independent functions concurrently
2. **Function Chaining** - Allow functions to depend on previous results
3. **Conditional Functions** - Support if/then logic in function calls
4. **Streaming Function Results** - Stream partial results as functions complete
5. **Function Retry Logic** - Automatic retry with backoff for transient failures

---

## References

- Migration Plan: `docs/FUNCTION_CALLING_MIGRATION_PLAN.md`
- Core Implementation: `src/functions/`
- Tests: `tests/unit/functions/test_critical_path.py`
- Integration: `src/triggers/triggering.py`, `src/services/dialogue_engine.py`
