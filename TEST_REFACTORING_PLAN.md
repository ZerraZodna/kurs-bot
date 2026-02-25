# Test Refactoring Plan

**Goal**: Improve test maintainability, reduce duplication, and make tests more readable and robust.

**Analysis Summary**:
- 66 test files (excluding conftest.py, helpers.py)
- ~148 test functions
- 19 files use mocking/patching
- 4 test files use class-based organization
- Largest files: test_integration_memory.py (371 lines), test_onboarding.py (343 lines), test_prompt_builder.py (341 lines)

---

## Phase 1: Consolidate Test Fixtures ✅ (In Progress)

### Issues Found:
1. **Duplicate DB session fixtures** - Almost every test file creates its own `db_session` fixture
2. **Inconsistent user creation** - Some use `create_test_user()`, others create inline
3. **Repetitive setup code** - Database initialization repeated across files
4. **Mixed fixture scopes** - Some "function", some "module", no clear pattern

### Actions:
- [ ] Create centralized `tests/fixtures/database.py` with:
  - `db_session` (function-scoped, clean DB per test)
  - `db_session_with_user` (includes default test user)
  - `db_engine` (session-scoped engine)
  
- [ ] Create `tests/fixtures/users.py` with:
  - `test_user` fixture (standard user)
  - `test_user_with_memories` fixture
  - `test_user_norwegian` fixture
  - User factory function for custom scenarios
  
- [ ] Create `tests/fixtures/services.py` with:
  - `memory_manager` fixture
  - `dialogue_engine` fixture
  - `scheduler_service` fixture
  - `embedding_service` fixture (mocked)

---

## Phase 2: Extract Common Test Utilities

### Issues Found:
1. **Assertion helpers scattered** - Similar assertions repeated across files
2. **Data builders duplicated** - Creating test memories, schedules, messages repeated
3. **Mock configurations repeated** - Same Ollama/embedding mocks in multiple files

### Actions:
- [ ] Create `tests/utils/assertions.py`:
  - `assert_memory_stored(db, user_id, key, expected_value)`
  - `assert_schedule_created(db, user_id, schedule_type)`
  - `assert_message_logged(db, user_id, direction, content_contains)`
  - `assert_onboarding_step(db, user_id, expected_step)`

- [ ] Create `tests/utils/builders.py`:
  - `MemoryBuilder` - fluent API for creating test memories
  - `ScheduleBuilder` - fluent API for creating schedules
  - `MessageBuilder` - fluent API for creating messages
  - `ConversationBuilder` - build multi-turn conversations

- [ ] Move mock configurations from `helpers.py` to `tests/mocks/`:
  - `ollama_mock.py` - Ollama client mocking
  - `embedding_mock.py` - Embedding service mocking
  - `httpx_mock.py` - HTTP client mocking

---

## Phase 3: Organize Tests by Feature Domain

### Current Structure Issues:
1. Tests are flat in `/tests` directory
2. No clear separation between unit, integration, and E2E tests
3. Related tests scattered across multiple files

### Proposed Structure:
```
tests/
├── unit/
│   ├── memory/
│   │   ├── test_memory_manager.py
│   │   ├── test_memory_extractor.py
│   │   └── test_semantic_search.py
│   ├── scheduler/
│   │   ├── test_scheduler_domain.py
│   │   └── test_scheduler_service.py
│   ├── language/
│   │   ├── test_language_detection.py
│   │   └── test_prompt_builder.py
│   └── onboarding/
│       └── test_onboarding_service.py
│
├── integration/
│   ├── test_memory_integration.py
│   ├── test_scheduler_integration.py
│   ├── test_trigger_integration.py
│   └── test_gdpr_api.py
│
├── e2e/
│   ├── test_onboarding_flow.py
│   ├── test_onboarding_flow_e2e.py
│   └── test_norwegian_onboarding.py
│
├── fixtures/
│   ├── database.py
│   ├── users.py
│   └── services.py
│
├── utils/
│   ├── assertions.py
│   └── builders.py
│
├── mocks/
│   ├── ollama_mock.py
│   ├── embedding_mock.py
│   └── httpx_mock.py
│
├── conftest.py (global fixtures)
└── helpers.py (deprecated - to be removed)
```

### Actions:
- [ ] Create new directory structure
- [ ] Move tests to appropriate directories
- [ ] Update imports in moved tests
- [ ] Update CI/CD test discovery paths

---

## Phase 4: Improve Test Readability

### Issues Found:
1. **Long test functions** - Some tests do too much
2. **Unclear test names** - Some names don't describe behavior
3. **Missing docstrings** - Hard to understand test purpose
4. **Magic values** - Hardcoded strings/numbers without explanation

### Actions:
- [ ] Apply naming convention: `test_<action>_<expected_result>`
  - Example: `test_store_memory_with_ttl_expires_after_time`
  
- [ ] Add Given-When-Then structure:
  ```python
  def test_onboarding_creates_schedule_after_completion():
      """When user completes onboarding, a daily schedule is auto-created."""
      # Given: A new user starting onboarding
      user = create_user(onboarding_complete=False)
      
      # When: User completes all onboarding steps
      complete_onboarding(user)
      
      # Then: A daily schedule should exist
      assert_schedule_created(user.user_id, "daily")
  ```

- [ ] Extract constants for magic values:
  ```python
  # Instead of:
  assert confidence == 0.95
  
  # Use:
  HIGH_CONFIDENCE = 0.95
  assert confidence == HIGH_CONFIDENCE
  ```

- [ ] Add parametrized tests for similar cases:
  ```python
  @pytest.mark.parametrize("time_string,expected", [
      ("9:00 AM", (9, 0)),
      ("2:30 PM", (14, 30)),
      ("morning", (9, 0)),
  ])
  def test_time_parsing(time_string, expected):
      assert parse_time(time_string) == expected
  ```

---

## Phase 5: Reduce Test Coupling

### Issues Found:
1. **Tests modify global state** - Scheduler initialization affects other tests
2. **Database state leaks** - Some tests don't clean up properly
3. **Test order dependencies** - Some tests assume previous test state

### Actions:
- [ ] Ensure all fixtures use proper cleanup:
  ```python
  @pytest.fixture
  def scheduler_service():
      SchedulerService.init_scheduler()
      yield SchedulerService
      SchedulerService.shutdown()  # Always cleanup
  ```

- [ ] Use transaction rollback for DB tests:
  ```python
  @pytest.fixture
  def db_session():
      connection = engine.connect()
      transaction = connection.begin()
      session = Session(bind=connection)
      
      yield session
      
      session.close()
      transaction.rollback()  # Rollback all changes
      connection.close()
  ```

- [ ] Isolate global mocks to test scope:
  ```python
  @pytest.fixture(autouse=True)
  def isolate_ollama_mock(monkeypatch):
      # Only affects current test
      monkeypatch.setattr(...)
      yield
      # Auto-cleanup by pytest
  ```

---

## Phase 6: Performance Optimization

### Issues Found:
1. **Slow DB initialization** - Every test recreates schema
2. **Redundant embedding generation** - Tests regenerate same embeddings
3. **No test parallelization** - Tests run sequentially

### Actions:
- [ ] Use template database approach (already in conftest):
  - Create DB once, copy for each test
  - Measure: Should reduce test time by 50%+

- [ ] Cache test embeddings:
  ```python
  @pytest.fixture(scope="session")
  def test_embeddings():
      return {
          "hello": [0.1, 0.2, ...],
          "goodbye": [0.3, 0.4, ...],
      }
  ```

- [ ] Enable pytest-xdist for parallel execution:
  - Add `pytest-xdist` to dev dependencies
  - Update CI: `pytest -n auto`
  - Mark non-parallel-safe tests: `@pytest.mark.serial`

---

## Phase 7: Documentation and Examples

### Actions:
- [ ] Create `tests/README.md`:
  - Explain test organization
  - How to run different test suites
  - How to add new tests
  - Common patterns and anti-patterns

- [ ] Add example test file:
  - `tests/examples/test_example.py`
  - Shows best practices
  - Templates for common test types

- [ ] Document fixture usage:
  - List all available fixtures
  - Usage examples
  - When to create new fixtures

---

## Progress Tracking

- [ ] Phase 1: Consolidate Test Fixtures (0/3 tasks)
- [ ] Phase 2: Extract Common Test Utilities (0/3 tasks)
- [ ] Phase 3: Organize Tests by Feature Domain (0/4 tasks)
- [ ] Phase 4: Improve Test Readability (0/4 tasks)
- [ ] Phase 5: Reduce Test Coupling (0/3 tasks)
- [ ] Phase 6: Performance Optimization (0/3 tasks)
- [ ] Phase 7: Documentation and Examples (0/3 tasks)

**Total Progress: 0/23 tasks completed**

---

## Success Metrics

- [ ] Test execution time reduced by >50%
- [ ] Zero test interdependencies (can run in any order)
- [ ] All tests have clear, descriptive names
- [ ] Test coverage maintained or improved (currently ~80%)
- [ ] New developer can understand test organization in <15 minutes
- [ ] Common test patterns documented and reusable

---

## Notes

- Keep existing tests running during refactoring
- Make small, incremental changes
- Run full test suite after each phase
- Update this document as work progresses
