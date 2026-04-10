"""Pure lesson delivery utilities.

Centralized logic for loading, previewing, formatting, and delivering lessons.
Used by scheduler, functions, onboarding, etc. No scheduling deps.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.orm import Session

from src.core.timezone import utc_now
from src.lessons.handler import format_lesson_message as handler_format_lesson_message
from src.lessons.importer import ensure_lessons_available
from src.lessons.state import compute_current_lesson_state, get_current_lesson, set_current_lesson
from src.memories import MemoryManager
from src.models.database import Lesson, User
from src.scheduler.message_utils import send_outbound_message

logger = logging.getLogger(__name__)


def _parse_lesson_int(value) -> int | None:
    """Safely parse lesson id to int."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s.isdigit():
            return int(s)
    return None


def get_lesson_or_import(db: Session, lesson_id: int) -> Lesson | None:
    """Load lesson; auto-import if missing (formerly scheduler._load_lesson)."""
    lesson = db.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
    if lesson:
        return lesson
    if ensure_lessons_available(db):
        return db.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
    return None


def build_lesson_preview(
    db: Session,
    memory_manager: MemoryManager,
    user_id: int,
    language: str,
) -> str | None:
    """Build preview message for no-last-sent (formerly scheduler._preview_build_for_no_last_sent)."""
    cur = get_current_lesson(memory_manager, user_id)
    lesson_id = _parse_lesson_int(cur)
    if lesson_id is not None:
        next_id = (lesson_id % 365) + 1
        lesson = get_lesson_or_import(db, next_id)
        if lesson:
            return asyncio.run(handler_format_lesson_message(lesson, language))
    # Fallback Lesson 1
    lesson = get_lesson_or_import(db, 1)
    if lesson:
        return asyncio.run(handler_format_lesson_message(lesson, language))
    return None


def deliver_lesson(
    db: Session,
    user_id: int,
    target_lesson_id: int | None,
    memory_manager: MemoryManager,
    language: str,
) -> None:
    """Deliver lesson: load, format, send, advance state (formerly scheduler._execute_lesson_schedule)."""

    # Compute/use target lesson
    if target_lesson_id is None:
        state = compute_current_lesson_state(memory_manager, user_id)
        target_lesson_id = state["lesson_id"]

    if target_lesson_id is None:
        return None
    lesson = get_lesson_or_import(db, target_lesson_id)
    if not lesson:
        logger.warning(f"No lesson {target_lesson_id} for user {user_id}")
        return None

    message = asyncio.run(handler_format_lesson_message(lesson, language))
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return None

    send_outbound_message(db, user, message)
    set_current_lesson(memory_manager, user_id, target_lesson_id)
    user.last_active_at = utc_now()
    db.commit()
    logger.info(f"Delivered lesson {target_lesson_id} to user {user_id}")
    return None
