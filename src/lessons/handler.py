"""Lesson retrieval and handling logic.

Lessons package only handles English text. Translation happens in language/translation_service.py ONLY.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from src.models.database import Lesson


logger = logging.getLogger(__name__)


def _find_lesson_by_id(session: Session, lesson_id: int) -> Lesson | None:
    """Lookup lesson by id and best-effort import bundled lessons when missing."""
    lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
    if lesson:
        return lesson

    from src.lessons.importer import ensure_lessons_available

    ok = ensure_lessons_available(session)
    if not ok:
        return None
    return session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()


def get_english_lesson_text(lesson: Lesson) -> str:
    """
    Format lesson as pure English text (lessons package responsibility ends here).

    Callers MUST translate if needed using src.language.translate_text().

    Args:
        lesson: Lesson object from database

    Returns:
        Raw English lesson text
    """
    return f"Lesson {lesson.lesson_id}: {lesson.title}\n\n{lesson.content}"
