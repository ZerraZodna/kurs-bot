# Lessons API Documentation

This document describes the public API for all lesson-related operations in Kurs Bot.

## Overview

The lessons module provides a unified public API through `src/lessons/api.py`. All lesson operations should use this facade rather than importing internal implementation modules.

## Public API

### Import Pattern
```python
from src.lessons import api as lessons_api
```

### Core Functions

#### `get_lesson(lesson_id, session)`
Retrieves a lesson by ID.

**Parameters:**
- `lesson_id` (int): The lesson ID
- `session` (Session): Database session

**Returns:** `Lesson` object or `None`

**Example:**
```python
lesson = lessons_api.get_lesson(1, session=db_session)
if lesson:
    print(f"Lesson {lesson.id}: {lesson.title}")
```

#### `format_lesson_message(lesson, language)`
Formats a lesson for display to the user.

**Parameters:**
- `lesson` (Lesson): The lesson object
- `language` (str): Language code ('en', 'no', etc.)

**Returns:** `str` - Formatted lesson message

**Example:**
```python
message = lessons_api.format_lesson_message(lesson, language='en')
```

#### `deliver_lesson(user_id, lesson_id, session, **kwargs)`
Delivers a lesson to a user through their configured channel.

**Parameters:**
- `user_id` (int): The user ID
- `lesson_id` (int): The lesson ID to deliver
- `session` (Session): Database session
- `language` (str, optional): Language code
- `call_ollama_fn` (callable, optional): Function to call Ollama for personalization

**Returns:** `dict` with delivery results

**Example:**
```python
result = lessons_api.deliver_lesson(
    user_id=123,
    lesson_id=5,
    session=db_session,
    language='en'
)
```

### State Management Functions

#### `get_current_lesson(memory_manager, user_id)`
Gets the current lesson ID for a user from memory.

**Parameters:**
- `memory_manager` (MemoryManager): The memory manager instance
- `user_id` (int): The user ID

**Returns:** `int` or `None` - The current lesson ID

#### `set_current_lesson(memory_manager, user_id, lesson_id)`
Sets the current lesson ID for a user in memory.

**Parameters:**
- `memory_manager` (MemoryManager): The memory manager instance
- `user_id` (int): The user ID
- `lesson_id` (int): The lesson ID to set

**Returns:** `bool` - True if successful

#### `get_last_sent_lesson_id(memory_manager, user_id)`
Gets the last lesson ID that was sent to the user.

**Parameters:**
- `memory_manager` (MemoryManager): The memory manager instance
- `user_id` (int): The user ID

**Returns:** `int` or `None` - The last sent lesson ID

#### `set_last_sent_lesson_id(memory_manager, user_id, lesson_id)`
Records the last lesson ID sent to the user.

**Parameters:**
- `memory_manager` (MemoryManager): The memory manager instance
- `user_id` (int): The user ID
- `lesson_id` (int): The lesson ID that was sent

**Returns:** `bool` - True if successful

#### `has_lesson_status(memory_manager, user_id)`
Checks if the user has any lesson status recorded.

**Parameters:**
- `memory_manager` (MemoryManager): The memory manager instance
- `user_id` (int): The user ID

**Returns:** `bool` - True if lesson status exists

#### `get_current_lesson_state(memory_manager, user_id)`
Gets the complete lesson state for a user.

**Parameters:**
- `memory_manager` (MemoryManager): The memory manager instance
- `user_id` (int): The user ID

**Returns:** `dict` with lesson state information

#### `compute_current_lesson_state(memory_manager, user_id, today)`
Computes the current lesson state based on user progress and today's date.

**Parameters:**
- `memory_manager` (MemoryManager): The memory manager instance
- `user_id` (int): The user ID
- `today` (date): Today's date

**Returns:** `dict` with computed state

### Query Processing

#### `process_lesson_query(user_id, query_text, session, **kwargs)`
Processes a lesson-related query from the user.

**Parameters:**
- `user_id` (int): The user ID
- `query_text` (str): The user's query text
- `session` (Session): Database session
- `language` (str, optional): Language code

**Returns:** `dict` with query results

### Advancement Functions

#### `maybe_send_next_lesson(user_id, session, **kwargs)`
Determines if the next lesson should be sent and sends it.

**Parameters:**
- `user_id` (int): The user ID
- `session` (Session): Database session
- `call_ollama_fn` (callable, optional): Function to call Ollama

**Returns:** `dict` with results

#### `apply_reported_progress(memory_manager, user_id, lesson_id)`
Applies user-reported progress to update lesson state.

**Parameters:**
- `memory_manager` (MemoryManager): The memory manager instance
- `user_id` (int): The user ID
- `lesson_id` (int): The lesson ID the user reported

**Returns:** `bool` - True if progress was applied

### Detection Functions

Lesson intent detection is available through `src/lessons/detection.py`:

#### `detect_lesson_request(text)`
Detects if a message contains a lesson-related request.

**Parameters:**
- `text` (str): The user message to analyze

**Returns:** `dict` or `None`
- If detected: `{"type": "lesson_request", "action": "...", "lesson_id": ...}`
- If not detected: `None`

**Example:**
```python
from src.lessons import detection as lessons_detection

result = lessons_detection.detect_lesson_request("Send me lesson 5")
# Returns: {"type": "lesson_request", "action": "send_lesson", "lesson_id": 5}
```

**Parameters:**
- `text` (str): The user's response about their lesson status

**Returns:** `dict` with status information
- `is_new_user` (bool): True if user is new
- `lesson_number` (int or None): Reported lesson number if continuing
- `has_completed_before` (bool): True if user completed course before

## Internal Modules (Do Not Import Directly)

The following modules are internal implementation details and should not be imported directly:

- `src.lessons.handler` - Lesson handling logic
- `src.lessons.state` - State management implementation
- `src.lessons.advance` - Lesson advancement logic
- `src.lessons.engine` - Lesson engine implementation
- `src.lessons.state_flow` - State flow management

**Always use the public API (`src.lessons.api`) instead.**

## Common Patterns

### Getting Current Lesson
```python
current_lesson_id = lessons_api.get_current_lesson(memory_manager, user_id)
if current_lesson_id:
    lesson = lessons_api.get_lesson(current_lesson_id, session)
    message = lessons_api.format_lesson_message(lesson, language='en')
```

### Setting User Progress
```python
# User reports they're on lesson 10
lessons_api.set_current_lesson(memory_manager, user_id, 10)
lessons_api.apply_reported_progress(memory_manager, user_id, 10)
```

### Checking Lesson Status
```python
if lessons_api.has_lesson_status(memory_manager, user_id):
    # User has lesson history
    state = lessons_api.get_current_lesson_state(memory_manager, user_id)
    print(f"Current lesson: {state.get('current_lesson_id')}")
else:
    # New user, no lesson history
    print("New user - start from lesson 1")
```

### Processing Lesson Query
```python
result = lessons_api.process_lesson_query(
    user_id=123,
    query_text="What is today's lesson?",
    session=db_session,
    language='en'
)
```

## Error Handling

All API functions handle common errors gracefully:

- **Lesson not found**: Returns `None`
- **Invalid lesson ID**: Returns `None` or raises `ValueError`
- **Database errors**: Logged and re-raised as appropriate exceptions

## Testing

Run lessons-specific tests:
```bash
pytest tests/ -k lesson -v
```

Key test files:
- `tests/unit/lessons/test_lesson_delivery.py`
- `tests/unit/lessons/test_next_day_confirmation.py`
- `tests/unit/onboarding/test_onboarding_fact_extraction.py`
