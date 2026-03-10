#!/usr/bin/env python3
"""Inspect user memories and list those related to lessons.

Usage: python scripts/inspect/inspect_memories.py [USER_ID]
If USER_ID is omitted, defaults to 7.
"""
import sys
import json
from src.models.database import init_db, Memory
from src.memories import MemoryManager


def is_lesson_memory(m):
    key = (m.key or "").lower()
    category = (m.category or "").lower()
    value = (m.value or "").lower()
    if "lesson" in key or "lesson" in category or "lesson" in value:
        return True
    if key in ("last_sent_lesson_id", "preferred_lesson_time"):
        return True
    return False


def as_dict(m):
    return {
        "memory_id": m.memory_id,
        "user_id": m.user_id,
        "category": m.category,
        "key": m.key,
        "value": m.value,
        "source": m.source,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def main():
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    init_db()
    mm = MemoryManager()

    q = mm.db.query(Memory).filter(
        Memory.user_id == user_id,
        Memory.is_active == True,
    ).order_by(Memory.created_at)

    rows = q.all()
    lesson_memories = [as_dict(r) for r in rows if is_lesson_memory(r)]

    out = {"user_id": user_id, "lesson_memories": lesson_memories}
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
