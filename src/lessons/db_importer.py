"""Database import functions for ACIM lessons."""

from __future__ import annotations

from typing import List

from src.core.clock import utc_now
from src.models.database import Lesson, SessionLocal


def import_to_db(
    lessons: List[tuple[int, str, str]],
    clear: bool = False,
    limit: int | None = None,
) -> int:
    """Import parsed lessons into the database.

    Args:
        lessons: List of (lesson_id, title, content) tuples.
        clear: If True, delete existing lessons before import.
        limit: Optional limit on number of lessons to import.

    Returns:
        Number of lessons added.
    """
    if limit is not None:
        lessons = lessons[:limit]
    added = 0
    with SessionLocal() as session:
        if clear:
            session.query(Lesson).delete()
            session.commit()
        for lid, title, content in lessons:
            exists = session.query(Lesson).filter(Lesson.lesson_id == lid).first()
            if exists:
                continue
            lesson = Lesson(
                lesson_id=lid,
                title=(title or "")[:128],
                content=content,
                difficulty_level="beginner",
                duration_minutes=15,
                created_at=utc_now(),
            )
            session.add(lesson)
            try:
                session.flush()
                added += 1
            except Exception:
                session.rollback()
                continue
            if added % 50 == 0:
                session.commit()
        session.commit()
    return added


def verify_db_count(expected: int) -> bool:
    """Verify the database contains the expected number of lessons."""
    with SessionLocal() as session:
        cnt = session.query(Lesson).count()
        print(f"Database contains {cnt} lessons (expected {expected})")
        return cnt >= expected
