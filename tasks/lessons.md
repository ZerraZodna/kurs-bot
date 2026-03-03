# Lessons Learned

## 2026-02-23 - Use repo test wrapper on this machine
- Root cause: I ran tests with ad-hoc commands (`python3 -m pytest` and mixed direct invocations), which can bypass the project wrapper and produce inconsistent behavior.
- Correct approach: run tests through the npm/venv wrapper so the correct interpreter and defaults are used.

