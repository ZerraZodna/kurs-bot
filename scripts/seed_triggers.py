"""Compatibility shim: delegate seeding to the TriggerMatcher implementation.

Seeding logic lives in `src.triggers.trigger_matcher.seed_triggers` to avoid
duplication; this script keeps the original CLI/API surface for callers and
tests that import `scripts.seed_triggers.main`.
"""
import asyncio

from src.triggers.trigger_matcher import seed_triggers


async def main():
    await seed_triggers()


if __name__ == '__main__':
    asyncio.run(main())
