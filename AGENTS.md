# Repository Guidelines

## Scope and Source of Truth
- This file is the canonical contributor and AI-agent workflow guide for this repository.
- `README.md` remains the source of truth for setup, runtime, and deployment.
- `CLAUDE.md` and `GEMINI.md` are adapter files and should only contain tool-specific deltas.

## Project Structure & Module Organization
- Main app code: `src/`.
- API and webhooks: `src/api/`; business logic: `src/services/`; memory stack: `src/memories/`; scheduling: `src/scheduler/`; integrations: `src/integrations/`; data models: `src/models/`.
- Tests: `tests/` (current pattern: `tests/test_*.py`).
- Migrations: `migrations/`; helper scripts: `scripts/`; docs: `docs/`; task tracking: `tasks/`.

## Build, Test, and Development Commands
- `npm install`: create `.venv` and install Python dependencies.
- `npm run init_db -- --db prod` or `npm run init_db -- --db dev`: initialize database.
- `npm start`: start local stack via helper scripts.
- `npm run start:foreground`: run API only (`uvicorn src.api.app:app --host 127.0.0.1 --port 8000`).
- `npm test`: run test suite through the project wrapper.
- `npm test -- tests/test_telegram_handler.py -q`: run targeted tests through the same wrapper.
- On this machine, prefer `npm test` / `node ./scripts/venv.js test` (see `tasks/lessons.md`).

## Engineering Workflow (All Contributors)
- Plan first for non-trivial work (3+ steps): write short checklist in `tasks/todo.md`.
- Implement smallest viable root-cause fix; avoid broad or speculative refactors unless requested.
- Verify before claiming done: run relevant tests and inspect diffs.
- After user-corrected mistakes, log a brief lesson in `tasks/lessons.md` (cause + prevention).

## Coding Style & Safety Rules
- Python: 4 spaces, `snake_case` for functions/variables, `PascalCase` for classes.
- Follow existing FastAPI, Pydantic, and SQLAlchemy ORM patterns.
- Do not add ad-hoc hard-coded command handlers without owner approval.
- Avoid silent exception handling (`except: pass`); prefer explicit handling and logging.
- Never expose secrets or user-specific data in code, logs, commits, or PR text.

## Testing and Pull Requests
- Test framework: `pytest` (`pytest.ini` uses `tests/`).
- Naming: `test_*.py` files and `test_*` functions.
- Add or update tests for behavior changes, bug fixes, and regressions.
- Keep commits focused and imperative (for example: `refactor: split dialogue scheduler checks`).
- PRs should include summary, rationale, test evidence, and migration/config impact.

## Key Architecture Docs (Read These First for Context)
- `docs/LESSON_DELIVERY_FLOW.md` — **Lesson state machine**: how `current_lesson` vs `last_sent_lesson_id` work, the day-by-day flow after onboarding, confirmation prompts, and `_semantic_yes_no` trigger dependency. Essential reading for any lesson/scheduler/onboarding work.
- `docs/EMBEDDINGS_TRIGGERS.md` — **Trigger embeddings pipeline**: STARTER list, `ci_trigger_data.py` generation, CI seeding, staleness detection, and the critical `confirm_yes`/`confirm_no` requirement.
- `docs/ONBOARDING.md` — Onboarding conversation flow.
- `TODO.md` — Current pending tasks and session context for continuity.

## Current Refactor Priorities
- Reorganize flat tests into module-based directories.
- Decompose `DialogueEngine.process_message` into smaller pipeline steps.
- Split `src/models/database.py` into module-based model files when safe.
