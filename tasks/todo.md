# Refactoring Progress

## 1. Modularize `src/models/database.py`
- [ ] Create `src/models/__init__.py` to export models
- [ ] Create `src/models/base.py` for Base, engine, and SessionLocal
- [ ] Move `User` to `src/models/user.py`
- [ ] Move `Memory` to `src/models/memory.py`
- [ ] Move `Lesson` and `Schedule` to `src/models/lesson.py`
- [ ] Move other models (GDPR, Logs, Triggers, PromptTemplate) to appropriate files
- [ ] Update imports across the codebase
- [ ] Verify with tests

