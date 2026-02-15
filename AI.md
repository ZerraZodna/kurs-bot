---
version: 1
created: 2026-02-15T00:00:00Z
---

READ THIS FIRST: Agents must open and read this file before making changes.

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
