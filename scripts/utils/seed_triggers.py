"""
Seed the default triggers into the database.

This is the canonical entrypoint under `scripts/utils/` — it exposes a
simple `seed()` function for programmatic use and runs synchronously when
invoked as a script.

The underlying implementation lives in `src.triggers.trigger_matcher.seed_triggers`
and is an async coroutine; this script runs it with `asyncio.run()`.
"""
import asyncio
from typing import Optional

from src.triggers.trigger_matcher import seed_triggers as _seed_triggers_coroutine


def seed() -> None:
    """Run the async seed coroutine in the current Python process.

    This function is idempotent: the underlying seeder performs upserts /
    skips to avoid duplicating data when re-run.
    """
    asyncio.run(_seed_triggers_coroutine())


def main(argv: Optional[list] = None) -> int:
    try:
        seed()
        print("✅ Triggers seeded")
        return 0
    except Exception as exc:
        print("❌ Failed to seed triggers:", exc)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
