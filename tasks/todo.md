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

## 6. Fix Invalid `lesson_completed` Memories (Priority 1)
- [x] Reproduce invalid extractor output storing `lesson_completed` values like `"last"` / `"current_lesson"`
- [x] Add strict validation in memory storage path: only allow numeric lesson ids (1-365) for `lesson_completed`
- [x] Reject/skip invalid `lesson_completed` values without creating memory rows
- [x] Ensure valid numeric `lesson_completed` writes still update lesson state correctly
- [x] Add regression tests for invalid and valid `lesson_completed` extraction cases
- [x] Run targeted memory/onboarding tests

## 7. Add User Preference To Skip Daily Confirmation Prompt (Priority 2)
- [x] Add a user memory/preference key to represent: auto-advance lessons without confirmation
- [x] Detect explicit user intent like "assume I do one lesson each day" and persist this preference
- [x] Update next-day confirmation flow to bypass confirmation when preference is enabled
- [x] Keep override path so user can still report "I did not do it" and pause/adjust progression
- [x] Add tests for enabled/disabled preference behavior and fallback handling
- [x] Run targeted lesson confirmation/scheduler tests

## 8. Improve Trigger Matching Observability and Coverage (Priority 3)
- [x] Add structured diagnostics for trigger decisions (matched action, score, threshold, and fallback path)
- [x] Ensure trigger-based intent handling is checked before strict regex fallbacks where appropriate
- [x] Add regression tests with paraphrased user inputs that should map to the same trigger intent
- [x] Add a lightweight debug command to explain why a message matched (or did not match) a trigger
- [x] Document trigger tuning workflow (how to add phrases, adjust thresholds, and verify with tests)
- [x] Run targeted trigger, dialogue, and scheduler tests

## 9. Add Admin Telegram Commands For Trigger Embeddings
- [x] Add admin-only command handler to add trigger phrase embeddings for existing actions
- [x] Add admin-only commands to list and delete trigger embeddings
- [x] Wire trigger admin commands into dialogue command stage
- [x] Add targeted tests for command parsing, auth guard, and DB writes/deletes
- [x] Document Telegram usage for trigger admin commands
- [x] Run targeted command/trigger/dialogue tests

## 10. Extract Trigger Admin Commands To Dedicated Module
- [x] Move trigger admin command logic out of `command_handlers.py` into `admin_handler.py`
- [x] Update dialogue exports/imports and tests to use the new module path
- [x] Run targeted trigger admin/command tests
