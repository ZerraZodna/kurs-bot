# CLAUDE.md

Adapter file for Claude Code.

## Primary Instructions
- Follow `AGENTS.md` as the canonical workflow and contribution guide.
- Use `README.md` for environment setup, runtime commands, and deployment details.

## Claude-Specific Notes
- When guidance overlaps across docs, prefer `AGENTS.md` for repository rules.
- Keep this file minimal; do not duplicate shared policies here.

- MANDATORY: Timezone handling ONLY via `src.core.timezone`. No direct imports of `datetime.timezone` or `zoneinfo`.
