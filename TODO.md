# TODO: Fix datetime.utcnow() deprecation
1. [x] Add `from datetime import UTC` to imports in 5 test files.
2. [ ] Replace all 23 `datetime.datetime.utcnow()` → `datetime.datetime.now(datetime.UTC)`.
3. [x] Test: pytest tests/unit/scheduler/test_scheduler_manager.py::TestSchedulerManager::test_create_get_update_deactivate -v
4. [ ] Full test: pytest tests/ -v --tb=short
5. [ ] pre-commit run --all-files
6. [ ] attempt_completion
