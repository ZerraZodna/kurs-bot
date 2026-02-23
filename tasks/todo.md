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

## 4. Onboarding Intro Step
- [x] Add a new onboarding pending step for intro confirmation after "new user" detection
- [x] Add localized onboarding prompt(s) for asking whether to send Lesson 0 now
- [x] Route affirmative response to deliver Lesson 0 (course introduction)
- [x] Keep negative/unclear responses in onboarding with clear next action
- [x] Update and run onboarding tests

## 5. Remove Legacy Onboarding Prompts Module
- [x] Replace `onboarding_prompts_legacy` imports with `onboarding_prompts`
- [x] Update tests to import the non-legacy prompt module
- [x] Delete `src/language/onboarding_prompts_legacy.py`
- [x] Run targeted tests covering onboarding, scheduler, and next-day confirmation
