# Refactoring Progress

## 2. Fix failing tests during migration to subfolders ✅
- [x] Diagnose root cause: `tests/fixtures/database.py` used `sqlite:///:memory:` while
      services (`TriggerMatcher`, `SchedulerService`) used `SessionLocal()` → file-based
      `test.db`. Two separate DBs → test data invisible to services.
- [x] Fix `tests/fixtures/database.py`: replace in-memory engine with app's `engine` +
      `SessionLocal` from `src.models.database`. Isolation still provided by
      `ensure_test_db` autouse fixture (drops/recreates tables per test).
- [x] Fix `tests/unit/onboarding/test_onboarding_flow.py`: add missing name-confirmation
      step (Hi → confirm name → consent → commitment → lesson status → intro offer).
- [x] Verified: 10/10 targeted tests pass, 225/225 full suite passes (no regressions).


## 1. Modularize `src/models/database.py`
- [ ] Create `src/models/__init__.py` to export models
- [ ] Create `src/models/base.py` for Base, engine, and SessionLocal
- [ ] Move `User` to `src/models/user.py`
- [ ] Move `Memory` to `src/models/memory.py`
- [ ] Move `Lesson` and `Schedule` to `src/models/lesson.py`
- [ ] Move other models (GDPR, Logs, Triggers, PromptTemplate) to appropriate files
- [ ] Update imports across the codebase
- [ ] Verify with tests

