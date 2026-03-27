# Test Suite Documentation

This document explains the organization and best practices for the test suite.

## Directory Structure

```
tests/
├── conftest.py              # Global fixtures and configuration
│
├── fixtures/                # Centralized test fixtures
│   ├── database.py          # DB session, engine fixtures
│   ├── users.py             # User fixtures and UserFactory
│   └── services.py          # Service fixtures (MemoryManager, etc.)
│
├── utils/                   # Test utilities
│   ├── assertions.py        # Assertion helpers
│   └── builders.py          # Fluent data builders
│
├── mocks/                   # Mock implementations
│   ├── ollama_mock.py       # Ollama client mocking
│   ├── embedding_mock.py    # Embedding service mocking
│   ├── httpx_mock.py        # HTTP client mocking
│   └── faiss_mock.py        # FAISS mocking
│
├── examples/                # Example tests (best practices)
│   └── test_example.py      # Reference implementation
│
├── unit/                    # Unit tests (to be populated)
│   ├── memory/
│   ├── scheduler/
│   ├── language/
│   └── onboarding/
│
├── integration/             # Integration tests (to be populated)
└── e2e/                   # End-to-end tests (to be populated)
```

## Quick Start

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/examples/test_example.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src --cov-report=html

# Run in parallel (requires pytest-xdist)
pytest -n auto
```

### Using Fixtures

Fixtures are automatically available via `conftest.py`. Common fixtures:

```python
def test_something(db_session, test_user, memory_manager):
    # db_session: Clean database session with transaction rollback
    # test_user: Pre-created test user
    # memory_manager: MemoryManager instance bound to db_session
    pass
```

### Available Fixtures

#### Database Fixtures (`tests/fixtures/database.py`)

- `db_engine` - Session-scoped database engine
- `db_connection` - Function-scoped connection with transaction
- `db_session` - Function-scoped session (primary fixture)
- `db_session_with_user` - Session with pre-created user
- `clean_db` - Fresh database (slower, use sparingly)

#### User Fixtures (`tests/fixtures/users.py`)

- `test_user` - Basic test user
- `test_user_with_memories` - User with onboarding memories
- `test_user_norwegian` - Norwegian language user
- `user_factory` - Factory for creating custom users

#### Service Fixtures (`tests/fixtures/services.py`)

- `memory_manager` - MemoryManager instance
- `dialogue_engine` - DialogueEngine instance
- `scheduler_service` - SchedulerService with auto-cleanup
- `mock_embedding_service` - Mocked embedding service
- `mock_ollama_client` - Mocked Ollama client
- `frozen_time` - Fixed datetime for time-based tests

### Using Builders

Fluent builders for creating test data:

```python
from tests.utils.builders import MemoryBuilder, ScheduleBuilder, ConversationBuilder

# Create a memory
memory = MemoryBuilder(db_session, user_id) \
    .with_key("goal") \
    .with_value("Learn Python") \
    .with_category("fact") \
    .with_confidence(0.9) \
    .build()

# Create a schedule
schedule = ScheduleBuilder(db_session, user_id) \
    .daily() \
    .at_time(9, 0) \
    .active() \
    .build()

# Create a conversation
messages = ConversationBuilder(db_session, user_id) \
    .user_says("Hello") \
    .bot_responds("Hi!") \
    .build()
```

### Using Assertion Helpers

Standardized assertions for common checks:

```python
from tests.utils.assertions import (
    assert_memory_stored,
    assert_memory_count,
    assert_schedule_created,
    assert_onboarding_complete,
    assert_response_contains,
)

# Assert memory exists
assert_memory_stored(db_session, user_id, "goal", expected_value="Learn Python")

# Assert memory count
assert_memory_count(db_session, user_id, 2, key="goal", is_active=True)

# Assert schedule created
assert_schedule_created(db_session, user_id, "daily")

# Assert onboarding complete
assert_onboarding_complete(db_session, user_id)

# Assert response contains text
assert_response_contains(response, "Welcome", "ACIM")
```

## Best Practices

### 1. Use Given-When-Then Structure

```python
def test_store_memory_creates_active_memory(self, db_session, test_user):
    """When storing a memory, it should be created as active."""
    # Given: A memory manager and test user
    mm = MemoryManager(db_session)

    # When: Storing a new memory
    memory_id = mm.store_memory(...)

    # Then: Memory should exist and be active
    assert_memory_stored(db_session, test_user.user_id, ...)
```

### 2. Use Descriptive Test Names

Follow the pattern: `test_<action>_<expected_result>`

```python
# Good
def test_store_memory_with_ttl_expires_after_time():
    pass

# Avoid
def test_memory_ttl():
    pass
```

### 3. Use Parametrized Tests for Multiple Cases

```python
@pytest.mark.parametrize("time_string,expected", [
    ("9:00 AM", (9, 0)),
    ("2:30 PM", (14, 30)),
    ("morning", (9, 0)),
])
def test_time_parsing(time_string, expected):
    assert parse_time(time_string) == expected
```

### 4. Extract Magic Values to Constants

```python
# Instead of:
assert confidence == 0.95

# Use:
HIGH_CONFIDENCE = 0.95
assert confidence == HIGH_CONFIDENCE
```

### 5. Use Fixtures for Common Setup

```python
# Good - use fixture
def test_something(db_session, test_user):
    pass

# Avoid - inline setup
def test_something():
    db = create_engine(...)
    user = create_test_user(...)
```

### 6. Clean Up After Tests

Use fixtures with proper cleanup:

```python
@pytest.fixture
def scheduler_service():
    SchedulerService.init_scheduler()
    yield SchedulerService
    SchedulerService.shutdown()
```

## Migration Guide

### From Old to New Fixtures

| Old Pattern | New Pattern |
|-------------|-------------|
| `db_session` fixture in each file | Import from `tests.fixtures.database` |
| `create_test_user(db, "id")` | Use `test_user` fixture or `user_factory` |
| `make_ready_user(db, "id")` | Use `test_user_with_memories` or `user_factory.create_ready_user()` |
| Inline memory creation | Use `MemoryBuilder` |
| Inline schedule creation | Use `ScheduleBuilder` |
| Inline mocks | Use `tests/mocks/` modules |

### Updating Existing Tests

1. Replace inline `db_session` fixtures with imports
2. Replace `create_test_user()` with `test_user` fixture
3. Replace manual memory creation with `MemoryBuilder`
4. Replace manual assertions with assertion helpers
5. Add Given-When-Then comments for clarity

## Troubleshooting

### Tests Are Slow

- Use `db_session` instead of `clean_db` when possible
- Use transaction rollback (default) instead of recreating schema
- Consider using `pytest-xdist` for parallel execution

### Database Isolation Issues

- Ensure you're using `db_session` fixture (not creating your own)
- Check that fixtures aren't leaking state between tests
- Use `db_session_with_user` for tests needing a user

### Mock Not Working

- Ensure mock is applied before the code under test runs
- Check that you're using the correct mock module
- For async mocks, use `AsyncMock` from `unittest.mock`

## Contributing

When adding new tests:

1. Place in appropriate directory (`unit/`, `integration/`, `e2e/`)
2. Use new fixtures from `tests/fixtures/`
3. Use builders and assertion helpers
4. Follow Given-When-Then structure
5. Add docstrings explaining test purpose
6. Run full test suite before committing
