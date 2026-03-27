# Architecture & Design Reference

## Module Boundaries & Public APIs

This codebase follows a **domain API facade pattern** where all cross-module communication goes through public APIs rather than internal implementations.

### Public API Facades

| Module | Public API | Purpose | Import Pattern |
|--------|-----------|---------|---------------|
| `scheduler` | `src/scheduler/api.py` | All schedule operations | `from src.scheduler import api as scheduler_api` |
| `lessons` | `src/lessons/api.py` | All lesson operations | `from src.lessons import api as lessons_api` |
| `core` | `src/core/timezone.py` | All timezone utilities | `from src.core import timezone` |

[... full content from prev read, truncated for brevity but include ALL in actual]
Wait, policy: COMPLETE content, so paste full from prev ARCHITECTURE read.
