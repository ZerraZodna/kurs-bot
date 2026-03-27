# Repository Guidelines

## Scope and Source of Truth
- This file is the canonical contributor and AI-agent workflow guide for this repository.
- `README.md` remains the source of truth for setup, runtime, and deployment.
- `CLAUDE.md` and `GEMINI.md` are adapter files and should only contain tool-specific deltas.

## Project Structure & Module Organization
- Main app code: `src/`.
- API and webhooks: `src/api/`; business logic: `src/services/`; memory stack: `src/memories/`; scheduling: `src/scheduler/`; integrations: `src/integrations/`; data models: `src/models/`.
- Shared utilities: `src/core/`; function calling: `src/functions/`; language & prompts: `src/language/`; lessons: `src/lessons/`; middleware: `src/middleware/`; onboarding: `src/onboarding/`; triggers: `src/triggers/`.
- Tests: `tests/` (current pattern: `tests/unit/*/test_*.py`, `tests/integration/test_*.py`).
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
- **Read relevant files first** to understand existing code, patterns, and infrastructure.
- **For non-trivial changes (>2 steps or potential deps):**
  1. IMMEDIATELY create `tasks/TODO.md` with DETAILED numbered step-by-step checklist from your analysis/plan.
  2. Response text: KEEP MINIMAL (e.g., "Created TODO.md for fix. Approve to proceed?").
  3. If TODO.md has more than 4 steps, ask **ONE** confirmation: "Approve TODO.md steps?". Simple bugs - JUST FIX!
  4. After approval: Execute steps, mark `[x]` in TODO.md per completion.
  5. Update TODO.md progressively to track progress.
- **Bugfixes/simple (1-2 steps):** Directly implement with tools (no TODO needed).
- **Always:** DRY – leverage existing code; no new solutions if current handles it.


## Coding Style & Safety Rules
- Python: 4 spaces, `snake_case` for functions/variables, `PascalCase` for classes.
- Follow existing FastAPI, Pydantic, and SQLAlchemy ORM patterns.
- Do not add ad-hoc hard-coded command handlers without owner approval.
- Never expose secrets or user-specific data in code, logs, commits, or PR text.

### Exception Handling Guidelines
- **No silent swallowing:** never write bare `except: pass`. Always log or re-raise.
- **Catch specific exceptions:** prefer `except ValueError` over `except Exception` unless you genuinely need a catch-all (e.g. protecting a critical loop from crashing).
- **Don't wrap logging in `try/except`:** if accessing an attribute for a log message can fail, use an `if` guard or `getattr(..., default)` instead of a `try/except` that itself calls the logger.
- **Reserve `try/except` for genuine failure boundaries:** external systems (APScheduler, HTTP calls, third-party libs) and I/O operations warrant `try/except`. Internal function calls and attribute access generally do not.
- **Fail fast on bad input:** validate inputs at function entry rather than catching parse errors deep inside the function body. If a helper like `parse_time_string` can fail, either validate before calling or have it return `None` instead of raising.
- **Keep `try` blocks small:** wrap only the statement(s) that can actually raise, not entire function bodies (unless it's a resource-cleanup `try/finally`).

### Session / Resource Management
- **Use context managers for DB sessions.** Do not repeat the manual `close_session = False; try/finally` pattern. Use the `get_session()` context manager (or equivalent) so cleanup is automatic:
  ```python
  # Good
  with get_session(session) as s:
      s.query(...)

  # Avoid — repetitive and error-prone
  close = False
  if session is None:
      session = SessionLocal()
      close = True
  try:
      ...
  finally:
      if close:
          session.close()
  ```
- When adding new functions that accept `session: Optional[Session] = None`, always use the context manager pattern.
- The same principle applies to any resource that needs cleanup (file handles, HTTP clients, etc.).

### Timezone Centralization (MANDATORY)
- ALL timezone operations MUST use ONLY `src.core.timezone` module
- BANNED everywhere else: `import datetime`, `from datetime import timezone`, `from zoneinfo`

## Testing and Pull Requests
- Standard command: `npm test`
- Targeted command: `npm test -- tests/test_telegram_handler.py tests/test_prompt_builder.py -q`
- Equivalent direct wrapper: `node ./scripts/venv.js test [pytest args]`
- Test framework: `pytest` (`pytest.ini` uses `tests/`). They can run in paralell too, but might fail with sql races.
- Naming: `test_*.py` files and `test_*` functions.
- Add or update tests for behavior changes, bug fixes, and regressions.
- Run tests in parallel with `pytest -n auto` (uses pytest-xdist) for faster execution.
- Keep commits focused and imperative (for example: `refactor: split dialogue scheduler checks`).

## Key Architecture Docs (Read These First for Context)
- `docs/LESSON_DELIVERY_FLOW.md` — **Lesson state machine**: how `current_lesson` vs `last_sent_lesson_id` work, the day-by-day flow after onboarding, confirmation prompts, and `_semantic_yes_no` trigger dependency. Essential reading for any lesson/scheduler/onboarding work.
- `docs/EMBEDDINGS_TRIGGERS.md` — **Trigger embeddings pipeline**: STARTER list, `ci_trigger_data.py` generation, CI seeding, staleness detection, and the critical `confirm_yes`/`confirm_no` requirement.
- `docs/ONBOARDING.md` — Onboarding conversation flow.
