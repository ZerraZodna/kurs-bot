# Repository Guidelines

## Scope and Source of Truth
- This file is the canonical contributor and AI-agent workflow guide for this repository.
- `README.md` remains the source of truth for setup, runtime, and deployment.
- `CLAUDE.md` and `GEMINI.md` are adapter files and should only contain tool-specific deltas.

## Task Management System (NEW)

### Master Task Tracker
- **Location**: `tasks/TODO_MASTER.md` — Central queue for ALL work items
- **Purpose**: Never lose context — see every bug/feature at a glance
- **Format**: Individual TODO files linked to master file

### Workflow
1. **Simple Bug Fixes (1-2 steps)**:
   - Create individual file: `tasks/TODO-fix_<name>.md`
   - Add entry to `tasks/TODO_MASTER.md`
   - Fix directly (no approval needed)

2. **Complex Changes (>2 steps)**:
   - Create detailed TODO.md in `tasks/`
   - Add entry to `tasks/TODO_MASTER.md`
   - Get approval before executing steps

3. **Multiple Bugs**:
   - Each bug gets its own individual TODO file
   - All tracked in `tasks/TODO_MASTER.md`
   - No context lost — everything visible!

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

### Task Registration (REQUIRED)
- **Before starting ANY work**, add entry to `tasks/TODO_MASTER.md`
- **Create individual TODO file** in `tasks/` for each work item
- **Never lose context** — master file shows ALL work in progress

### Simple Bug Fixes (1-2 steps)
- Create individual file: `tasks/TODO-fix_<name>.md`
- Add entry to `tasks/TODO_MASTER.md`
- Fix directly with tools (no approval needed)

### Non-Trivial Changes (>2 steps or potential deps)
- Create detailed `tasks/TODO_<name>.md` with numbered steps
- Add entry to `tasks/TODO_MASTER.md`
- Response: "Created TODO.md for [task]. Approve to proceed?"
- If >4 steps, ask: "Approve TODO.md steps?"
- After approval: Execute steps, mark `[x]` in TODO.md per completion

### Multiple Bugs
- Each bug gets its own individual TODO file
- All tracked in `tasks/TODO_MASTER.md`
- Fix them one at a time (no context lost!)

### Always
- **DRY** – leverage existing code; no new solutions if current handles it.
- **Check `tasks/TODO_MASTER.md` first** before starting work


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
- `swarm/TODO.md` — **3-Tier Supervisor Architecture**: Anti-drift coding system with Architect → Code Writer → Reviewer → Pre-Commit workflow. REQUIRED for all coding tasks.

## Anti-Drift Coding System (swarm/ & subagent pattern)

### Overview
The anti-drift coding system prevents scope creep and maintains task boundaries through a 4-tier supervisor architecture:

1. **Architect**: Defines task with STRICT constraints
2. **Code Writer**: Implements changes (outputs ONLY unified git diff)
3. **Reviewer**: Validates anti-drift compliance
4. **Pre-Commit Runner**: Runs tests before final approval

### Usage: swarm CLI
**Prerequisites**: Local LLM server running at `localhost:8080/v1`

**Command format:**
```bash
node ./scripts/venv.js exec -m swarm.cli "Your task description here"
```

**Example:**
```bash
node ./scripts/venv.js exec -m swarm.cli "Add max_retries=3 to swarm/config.py"
```

**Expected output:**
```
Step 1/3: Architect planning...
Step 2/3: Code writer generating...
Step 3/3: Review complete!
📝 Reviewer feedback: ✅ Approved
✅ Task completed successfully!
--- PROPOSED DIFF ---
[unified git diff for files in swarm/ only]
```

**⚠️ Timeout Warning**: LLM calls may take 60s+. Set appropriate timeout if needed.

### Usage: Subagent Pattern (Recommended)
**No LLM required** - Works everywhere, faster than swarm CLI

**Command format:**
```python
delegate_task(
    goal="Clear task description with STRICT constraints",
    context="[Anti-drift rules: output ONLY unified git diff, stay in designated folder only...]",
    toolsets=["terminal", "file"]
)
```

**Example:**
```python
delegate_task(
    goal="Create swarm/TODO.md documenting the 3-tier architecture",
    context="Anti-drift rules: output ONLY unified git diff, DO NOT write full files, DO NOT touch files outside swarm/, DO NOT add extra functions or tests, DO NOT modify imports in existing files, DO NOT change existing swarm/ code, DO NOT use markdown, just plain diff. If you violate any rule, the REVIEWER will reject you.",
    toolsets=["terminal", "file"]
)
```

**Benefits:**
- ✅ **Faster**: ~24s vs ~60s+
- ✅ **No timeout**: No LLM dependency
- ✅ **More reliable**: Human-in-the-loop
- ✅ **Works everywhere**: No infrastructure needed

### Anti-Drift Rules (MUST follow)
**For ALL coding tasks:**
- Output ONLY a unified git diff
- DO NOT write full files
- DO NOT touch files outside designated scope
- DO NOT add extra functions or tests
- DO NOT modify imports in existing files
- DO NOT change existing code
- DO NOT use markdown in output
- Keep changes minimal and focused

### Workflow (4-Tier)
```
1. Architect → Define task with STRICT constraints
   ↓
2. Code Writer → Execute (output ONLY unified git diff)
   ↓
3. Reviewer → Validate compliance
   ↓
4. Pre-Commit → Run tests (npm test / pytest)
   ↓
5. You → Final approval to commit/push
```

### Documentation
- `swarm/TODO.md` — Architecture documentation
- `SWARM_SUBAGENT_PATTERN.md` — Subagent pattern guide
- `swarm/cli.py` — CLI implementation (requires LLM)

**IMPORTANT**: Always test changes in a local branch before pushing. Never commit without running tests first.
