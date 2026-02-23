# Refactoring Progress

## 1. Decompose `DialogueEngine.process_message`
- [x] Extract GDPR and State validation stage
- [x] Extract Language and RAG configuration stage
- [x] Extract Command handling stage (forget, debug, schedule deletion)
- [x] Extract Onboarding stage
- [x] Extract Lesson and Schedule handling stage
- [x] Extract LLM Prompt and Response generation stage
- [x] Verify with tests

## 3. Modularize `src/models/database.py`
- [ ] Create `src/models/__init__.py` to export models
- [ ] Create `src/models/base.py` for Base, engine, and SessionLocal
- [ ] Move `User` to `src/models/user.py`
- [ ] Move `Memory` to `src/models/memory.py`
- [ ] Move `Lesson` and `Schedule` to `src/models/lesson.py`
- [ ] Move other models (GDPR, Logs, Triggers, PromptTemplate) to appropriate files
- [ ] Update imports across the codebase
- [ ] Verify with tests
