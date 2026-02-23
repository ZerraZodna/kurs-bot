# GEMINI.md

This file provides guidance to Gemini CLI when working with code in this repository.

## Project Overview
Kurs Bot is a spiritual coaching chatbot delivering ACIM (A Course in Miracles) lessons. It uses FastAPI, SQLAlchemy, Ollama (LLM), and APScheduler.

## Engineering Standards

### Core Lifecycle
1. **Research**: Map the codebase and validate assumptions using `grep_search` and `glob`.
2. **Strategy**: Formulate a plan and share a concise summary.
3. **Execution**: Iterative Plan -> Act -> Validate cycle.

### Rules & Mandates
- **Precedence**: This file (`GEMINI.md`) takes precedence over general defaults.
- **Testing**: ALWAYS search for and update related tests after code changes. Add new test cases for new features or bug fixes.
- **Refactoring**: Prioritize readability and maintainability. Decompose monolithic methods (like `DialogueEngine.process_message`).
- **Security**: Never log or commit secrets. Protect `.env` and `.git` folders.
- **Conventions**: Adhere to existing patterns (SQLAlchemy ORM, FastAPI, Pydantic).

## Refactoring Roadmap (Current Priorities)

### 1. Test Organization
The `tests/` directory is flat and overcrowded (50+ files).
- **Goal**: Group tests by module (e.g., `tests/api/`, `tests/memories/`, `tests/scheduler/`, `tests/services/`).
- **Action**: Create subdirectories and move relevant test files.

### 2. DialogueEngine Decomposition
`DialogueEngine.process_message` is a monolithic method (250+ lines).
- **Goal**: Refactor into a "Pipeline" or "Chain of Responsibility" pattern.
- **Steps**:
  - Extract GDPR handling to a method.
  - Extract RAG/Memory extraction to a method.
  - Extract Onboarding logic to a method.
  - Extract Lesson/Schedule logic to a method.

### 3. Model Organization
`src/models/database.py` contains all models.
- **Goal**: Split into `src/models/user.py`, `src/models/lesson.py`, `src/models/memory.py`, etc.
- **Action**: Use a package structure for `src/models/`.

### 4. Documentation & Scripts
- **Goal**: Consolidate `docs/` and categorize `scripts/`.

## Development Commands
(See `CLAUDE.md` for full list)
- Run tests: `python -m pytest tests/`
- Run server: `uvicorn src.api.app:app --reload`
- Migrations: `alembic upgrade head`
