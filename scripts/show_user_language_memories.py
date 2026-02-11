"""Show all active `user_language` memories in the configured DB."""
from __future__ import annotations

from src.models.database import SessionLocal, Memory


def main():
    db = SessionLocal()
    try:
        rows = db.query(Memory).filter(Memory.key == "user_language").order_by(Memory.user_id, Memory.memory_id).all()
        if not rows:
            print("No user_language memories found.")
            return
        print(f"Found {len(rows)} user_language memories (active flag shown):")
        for r in rows:
            print(f"memory_id={r.memory_id} user_id={r.user_id} value='{r.value}' active={r.is_active} category={r.category} created_at={r.created_at}")
    finally:
        db.close()


if __name__ == '__main__':
    main()
