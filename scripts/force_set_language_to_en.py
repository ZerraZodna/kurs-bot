"""Utility script: force all `user_language` memories to 'en'.

Usage:
  python scripts/force_set_language_to_en.py        # dry-run, shows changes
  python scripts/force_set_language_to_en.py --apply  # actually write changes
"""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
from typing import List

from src.models.database import SessionLocal, Memory, init_db


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def find_user_language_memories(db) -> List[Memory]:
    return db.query(Memory).filter(Memory.key == "user_language", Memory.is_active == True).all()


def main(dry_run: bool = True):
    init_db()
    db = SessionLocal()
    try:
        rows = find_user_language_memories(db)
        print(f"Found {len(rows)} active 'user_language' memories")
        changes = []
        now = datetime.now(timezone.utc)
        for r in rows:
            old = r.value
            if old == "en":
                continue
            new = "en"
            changes.append((r.memory_id, r.user_id, old, new))

        if not changes:
            print("No non-'en' user_language memories found. Nothing to do.")
            return 0

        print("Sample changes (showing up to 20):")
        for mid, uid, old, new in changes[:20]:
            print(f"  memory_id={mid} user_id={uid} : '{old}' -> '{new}'")

        print(f"Total changes: {len(changes)}")
        if dry_run:
            print("Dry-run mode; no changes written. Re-run with --apply to persist.")
            return 0

        # Apply updates
        for mid, uid, old, new in changes:
            r = db.query(Memory).filter(Memory.memory_id == mid).one()
            r.value = new
            r.value_hash = hash_value(new)
            r.updated_at = now
            r.confidence = max(r.confidence or 0.0, 1.0)
            db.add(r)
        db.commit()
        print(f"Applied {len(changes)} updates.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Persist changes to the database")
    args = parser.parse_args()
    exit(main(dry_run=not args.apply))
