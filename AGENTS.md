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
- Run tests in parallel with `pytest -n auto` (uses pytest-xdist) for faster execution.
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

<!-- gitnexus:start -->
# GitNexus MCP

This project is indexed by GitNexus as **kurs-bot** (1705 symbols, 5113 relationships, 129 execution flows).

GitNexus provides a knowledge graph over this codebase — call chains, blast radius, execution flows, and semantic search.

## Always Start Here

For any task involving code understanding, debugging, impact analysis, or refactoring, you must:

1. **Read `gitnexus://repo/{name}/context`** — codebase overview + check index freshness
2. **Match your task to a skill below** and **read that skill file**
3. **Follow the skill's workflow and checklist**

> If step 1 warns the index is stale, run `npx gitnexus analyze` in the terminal first.

## Skills

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/refactoring/SKILL.md` |

## Tools Reference

| Tool | What it gives you |
|------|-------------------|
| `query` | Process-grouped code intelligence — execution flows related to a concept |
| `context` | 360-degree symbol view — categorized refs, processes it participates in |
| `impact` | Symbol blast radius — what breaks at depth 1/2/3 with confidence |
| `detect_changes` | Git-diff impact — what do your current changes affect |
| `rename` | Multi-file coordinated rename with confidence-tagged edits |
| `cypher` | Raw graph queries (read `gitnexus://repo/{name}/schema` first) |
| `list_repos` | Discover indexed repos |

## Resources Reference

Lightweight reads (~100-500 tokens) for navigation:

| Resource | Content |
|----------|---------|
| `gitnexus://repo/{name}/context` | Stats, staleness check |
| `gitnexus://repo/{name}/clusters` | All functional areas with cohesion scores |
| `gitnexus://repo/{name}/cluster/{clusterName}` | Area members |
| `gitnexus://repo/{name}/processes` | All execution flows |
| `gitnexus://repo/{name}/process/{processName}` | Step-by-step trace |
| `gitnexus://repo/{name}/schema` | Graph schema for Cypher |

## Graph Schema

**Nodes:** File, Function, Class, Interface, Method, Community, Process
**Edges (via CodeRelation.type):** CALLS, IMPORTS, EXTENDS, IMPLEMENTS, DEFINES, MEMBER_OF, STEP_IN_PROCESS

```cypher
MATCH (caller)-[:CodeRelation {type: 'CALLS'}]->(f:Function {name: "myFunc"})
RETURN caller.name, caller.filePath
```

<!-- gitnexus:end -->
