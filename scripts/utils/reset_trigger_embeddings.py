"""Reset trigger embeddings to the canonical STARTER set.

This deletes all rows in the `trigger_embeddings` table and re-seeds
the starter set defined in `src.triggers.trigger_matcher.STARTER` using
the currently configured embedding backend/model.

Usage:
    PYTHONPATH=. python scripts/utils/reset_trigger_embeddings.py

Be aware: this will remove any custom trigger embeddings persisted in
the DB; use only when you can safely lose or recreate those entries.
"""
from __future__ import annotations
import sys
from pathlib import Path
import asyncio


def _ensure_repo_root_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_ensure_repo_root_on_path()


async def main() -> int:
    print("⚠️  This will delete all rows in trigger_embeddings and re-seed STARTER")
    from src.models.database import SessionLocal, TriggerEmbedding
    from src.triggers.trigger_matcher import seed_triggers

    db = SessionLocal()
    try:
        num = db.query(TriggerEmbedding).count()
        if num > 0:
            print(f"Deleting {num} existing trigger_embeddings rows...")
            db.query(TriggerEmbedding).delete()
            db.commit()
            print("Deleted existing trigger embeddings.")
        else:
            print("No existing trigger embeddings found; seeding starter set.")
    finally:
        db.close()

    print("Seeding STARTER trigger embeddings using current embedding backend...")
    try:
        await seed_triggers()
        print("✅ Re-seeded trigger embeddings from STARTER")
    except Exception as e:
        print(f"⚠️  Failed to seed trigger embeddings: {e}")
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
