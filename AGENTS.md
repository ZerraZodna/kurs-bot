# Repository Guidelines

## Project Structure & Module Organization
- Core application code lives in `src/`:
- `src/api/` (FastAPI entrypoints and routes), `src/services/` (business logic), `src/memories/` (memory system), `src/scheduler/` (lesson/reminder jobs), `src/integrations/` (Telegram/Slack/etc.), `src/models/` (SQLAlchemy models).
- Tests are in `tests/` and currently mostly flat (`tests/test_*.py`).
- Database migrations are in `migrations/`.
- Utility scripts are in `scripts/`; static assets are in `static/`; operational notes are in `docs/` and `tasks/`.

## Build, Test, and Development Commands
- `npm install`: creates `.venv` and installs Python dependencies via project helper scripts.
- `npm run init_db -- --db prod` (or `--db dev`): initialize database schema and seed required data.
- `npm start`: start API (and ngrok if available in environment).
- `npm run start:foreground`: run only the API locally (`uvicorn` on `127.0.0.1:8000`).
- `npm test` or `python -m pytest tests/ -v`: run test suite.
- `npm run test:fast`: quick pytest run (`--maxfail=3 -q`).

## Coding Style & Naming Conventions
- Python style: 4-space indentation, `snake_case` for functions/variables, `PascalCase` for classes, clear module names (`src/services/dialogue_engine.py` style).
- Prefer small, focused changes; fix root causes rather than surface patches.
- Use SQLAlchemy ORM patterns already present in the repo; avoid ad-hoc raw SQL unless necessary.
- Keep error handling explicit; avoid broad silent `except` blocks.
- `npm run lint` currently reports no configured linter, so follow existing code patterns and keep imports/types tidy.

## Testing Guidelines
- Framework: `pytest` (`pytest.ini` points to `tests/`).
- Naming: test files as `test_*.py`; test functions as `test_*`.
- Add or update tests for every behavior change or bug fix, especially around `src/services/`, `src/memories/`, and API routes.
- Run targeted tests during development, then a broader suite before opening a PR.

## Commit & Pull Request Guidelines
- Recent history uses terse messages (for example: `lazy import`, `refactor jobs`); prefer concise imperative messages with scope, such as `refactor: split dialogue scheduler checks`.
- Keep commits small and single-purpose.
- PRs should include: what changed, why, test evidence (commands run), and any config/migration impact.
- Link related issues/tasks and call out risks or follow-ups explicitly.

## Security & Configuration Tips
- Never commit secrets; use `.env` from `.env.template`.
- Required tokens include bot/auth/GDPR values documented in `README.md`.
- Treat user memory and logs as sensitive; avoid exposing personal data in debug output.
