#!/usr/bin/env python3
"""Print key status counts from the currently configured database."""

import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.models.database import (  # noqa: E402
    Lesson,
    MessageLog,
    SessionLocal,
    User,
)
from src.models.memory import Memory
from src.config import settings


def main() -> int:
    db = SessionLocal()
    try:
        active_users = (
            db.query(User)
            .filter(
                User.opted_in.is_(True),
                User.processing_restricted.is_(False),
                User.is_deleted.is_(False),
            )
            .count()
        )
        lessons = db.query(Lesson).count()
        messages = db.query(MessageLog).count()

        print(f"database_url: {settings.DATABASE_URL}")
        print(f"active_users: {active_users}")
        print(f"lessons: {lessons}")
        print(f"messages: {messages}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
