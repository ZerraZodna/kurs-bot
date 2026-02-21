# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kurs Bot is a spiritual coaching chatbot that delivers daily ACIM (A Course in Miracles) lessons via Telegram, Slack, SMS, and email. It features persistent user memory, AI-powered dialogue (via Ollama), and GDPR-compliant data handling.

## Development Commands
As first command, ensure that ./.venv/ is activated.

```bash
# Setup
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
alembic upgrade head

# Run development server
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000

# Run tests
python -m pytest tests/ -v
# or on Windows:
.\run_tests.ps1

# Run single test file
python -m pytest tests/test_memory_manager.py -v

# Run single test function
python -m pytest tests/test_memory_manager.py::test_store_memory -v

# Database CLI (common tasks)
python cli.py db status          # Show database status
python cli.py db reset           # Reset dev.db (keeps 365 lessons)
python cli.py import-lessons     # Import ACIM lessons from PDF
```

## Architecture

**Entry Point**: `src/api/app.py` - FastAPI app with webhooks for Telegram/Slack, lifespan management for scheduler and background tasks.

**Core Flow**:
1. Webhook receives message → routes to `DialogueEngine.process_message()`
2. `DialogueEngine` orchestrates: onboarding check → memory retrieval → prompt assembly → Ollama LLM call → memory extraction → response
3. `MemoryManager` handles persistent user context (preferences, goals, progress)
4. `SchedulerService` manages daily lesson delivery and one-time reminders

**Key Modules**:
- `src/services/dialogue_engine.py` - Main orchestration for message processing
- `src/memories/` - Memory storage, extraction, and classification
- `src/scheduler/` - APScheduler-based lesson delivery and reminders
- `src/onboarding/` - New user setup flow (language, timezone, schedule)
- `src/triggers/` - Embedding-based trigger matching for commands
- `src/services/prompt_builder.py` - Assembles context blocks for LLM

**Database**: SQLAlchemy ORM with SQLite (dev) / SQL Server (prod). Models in `src/models/database.py`. Migrations via Alembic.

**Embeddings**: Two backends via `EMBEDDING_BACKEND` env var:
- `local`: sentence-transformers (all-MiniLM-L6-v2, 384-dim)
- `ollama`: Ollama API with nomic-embed-text (768-dim)

## Agent Workflow Rules

From `AGENT_INSTRUCTIONS.md`:
1. **Plan first** - For non-trivial tasks (3+ steps), write a plan into `tasks/todo.md` before editing code
2. **Verify before done** - Run relevant tests and show diffs; provide proof the change works
3. **Root cause fixes** - Fix underlying issues, not symptoms; avoid surface patches
4. **Self-improve** - After corrections, add entries to `tasks/lessons.md` describing root cause and fix

## Key Constraints

- Do NOT add ad-hoc command handlers without explicit owner approval
- User data safety: never expose secrets or user-specific data in outputs
- Use SQLAlchemy ORM for DB queries; wrap raw SQL with `text(...)`
- Avoid silent `try/except` blocks - prefer explicit error handling and logging

## Configuration

Environment variables in `.env` (see `.env.template`):
- `DATABASE_URL` - SQLite or SQL Server connection string
- `TELEGRAM_BOT_TOKEN`, `SLACK_BOT_TOKEN` - Channel integrations
- `OLLAMA_MODEL`, `OLLAMA_EMBED_URL` - LLM and embedding settings
- `EMBEDDING_BACKEND` - "local" or "ollama"
- `GDPR_ADMIN_TOKEN`, `API_AUTH_TOKEN` - Security tokens

## Documentation

Key docs in `docs/`:
- `ARCHITECTURE.md` - Detailed system architecture and data flow diagrams
- `DATABASE_GUIDE.md` - Database operations guide
- `ONBOARDING.md` - Onboarding flow documentation
- `MEMORY_CONTEXT_SYSTEM.md` - Memory system design

## Guidelines

Purpose
- Single authoritative onboarding for AI agents working in this repository.
- Short, machine- and human-friendly rules to reduce ambiguity and prevent regressions.

Workflow Orchestration

1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions).
- If something goes sideways, STOP and re-plan immediately — do not keep pushing.
- Use plan mode for verification steps, not just building.
- Write a short actionable plan into `tasks/todo.md` before editing code.

2. Subagent Strategy
- Offload research, exploration, and parallel analysis to subagents to keep the main context window clean.
- For complex problems, spawn focused subagents (one task per subagent) and gather concise results.

3. Self-Improvement Loop
- After ANY correction from the user: add an entry to `tasks/lessons.md` describing root cause and the fix.
- Add rules to prevent the same mistake from recurring and review lessons at session start.

4. Verification Before Done
- Never mark a task complete without proving it works: run relevant tests, check logs, and show diffs.
- Ask: "Would a staff engineer approve this?"

5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?" and prefer small, well-scoped refactors.
- If a fix feels hacky, replace with an elegant solution unless that would be over-engineering.

6. Autonomous Bug Fixing
- When given a bug report: fix it directly (find root cause), run tests, and point to failing tests/logs.
- Avoid asking the user for unnecessary context or hand-holding.

Task Management
1. `tasks/todo.md` — Plan first and list checkable steps.
2. `tasks/lessons.md` — Record lessons after fixes.
3. Update `src/memories/permanent_memory.json` only when you intentionally seed persistent agent-visible data.

Core Principles
- Simplicity First: smallest change that solves root cause.
- No Laziness: find root causes; avoid temporary hacks.
- Minimal Impact: touch only what is necessary; prefer tests and verification.

No Duplication
- Do not duplicate information across files or docs. Keep a single source of truth (prefer `AI.md` at repo root).
- If supporting artifacts are needed (e.g. `tasks/todo.md`, `tasks/lessons.md`), link them from `AI.md` rather than duplicating rules.

If you are an automated agent, STOP and write a plan into `tasks/todo.md` before editing code. If `tasks/todo.md` does not exist, create it and commit the plan.

Repository Assistant Constraints (from COPILOT_INSTRUCTIONS)

- Do NOT insert ad-hoc, high-level, or hard-coded command handlers into production code without explicit approval from the repository owner.
- All code changes made by AI assistants must be small, focused, and documented in the pull request description. Include tests or ensure tests are run locally before committing.
- Present options and ask for explicit permission when a requested behavioral change cannot be implemented safely within a single function or service.
- For language/UX overrides or new user-facing commands: confirm design and tests first with a human reviewer.
- Automated tools or bots modifying the repo should stop, notify the user, and request explicit permission before making changes.
- Avoid broad `try: except:` swallowing errors in code paths that must run; prefer explicit error handling and logging. Do not use silent `except: pass` in production code.

Maintainers: add a note in your PR template or `CONTRIBUTING.md` referencing this file to enforce the policy.