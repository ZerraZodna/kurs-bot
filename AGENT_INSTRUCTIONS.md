"""
Agent Instructions — concise rules for automated assistants working in this repo.

This file consolidates the actionable agent guidance from `AI.md`.

Keep changes small, verified, and documented. Follow these rules every session.
"""

1) Environment
- Activate the project virtualenv before running Python commands.
- Run commands from the repository root or ensure `PYTHONPATH` contains the project root so `import src` works.

2) Plan First
- For non-trivial tasks (3+ steps or architectural decisions) write a short plan into `tasks/todo.md` first.
- Use the repo TODO mechanism (`manage_todo_list`) to track progress and status.

3) Research & Subagents
- Offload exploratory work and parallel searches to subagents to keep the main context focused.
- Spawn one focused subagent per research task and gather concise results.

4) Code Changes — Scope & Style
- Make small, well-scoped edits. Fix root causes rather than applying surface patches.
- Prefer clarity and minimal impact: touch only what's necessary and keep public APIs stable.
- Do not add ad-hoc, high-level, or hard-coded command handlers without explicit owner approval.

5) Verification Before Done
- Run relevant tests and show diffs before marking work complete.
- Provide proof the change works (test output, log excerpts, or CI commands that pass).

6) Testing & CI
- Add or update tests where appropriate for behavioral changes.
- Run the repository’s test suite locally when modifying logic (use run_tests.ps1 on Windows).

7) DB & PowerShell Guidance
- Prefer SQLAlchemy ORM queries for DB changes; if raw SQL is required wrap strings with `text(...)`.
- When providing PowerShell CLI examples: wrap outer argument in double quotes and inner Python/SQL string literals in single quotes.
- Run DB-affecting commands only after confirming intent and in a venv from the repo root.

8) Safety & Privacy
- Do not expose secrets, credentials, or user-specific data in outputs.
- For the dev Web UI ignore any client-supplied `user_id`; use server-derived identifiers or require authentication.
- When asked to modify or export real user data, request explicit human approval.

9) Self-Improvement & Lessons
- After any correction or root-cause fix, add a short entry to `tasks/lessons.md` describing the cause and the fix.

10) Change Control & Communication
- If a requested change is broad, risky, or architectural, present options and ask for explicit permission.
- Avoid silent broad `try/except` blocks; prefer explicit error handling and logging.

11) Referenced Files (authoritative)
- `AI.md` — authoritative agent onboarding and rules.
- `AGENT_INSTRUCTIONS.md` — concise agent-facing checklist (this file).

Keep this file short and actionable. If you want changes to the tone or additional automation rules, propose them as a short plan in `tasks/todo.md`.
