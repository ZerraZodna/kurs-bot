"""Pure lesson delivery utilities.

Centralized logic for loading, previewing, formatting, and delivering lessons.
Used by scheduler, functions, onboarding, etc. No scheduling deps.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from src.core.timezone import utc_now
from src.lessons.handler import format_lesson_message as handler_format_lesson_message
from src.lessons.importer import ensure_lessons_available
from src.lessons.state import compute_current_lesson_state, get_current_lesson, set_current_lesson
from src.memories import MemoryManager
from src.models.database import Lesson, User
from src.scheduler.message_utils import send_outbound_message

logger = logging.getLogger(__name__)


def _parse_lesson_int(value) -> Optional[int]:
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


def get_lesson_or_import(db: Session, lesson_id: int) -> Optional[Lesson]:
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
) -> Optional[str]:
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
    target_lesson_id: Optional[int],
    memory_manager: MemoryManager,
    simulate: bool = False,
    language: Optional[str] = None,
) -> List[str]:
    """Deliver lesson: load, format, send, advance state (formerly scheduler._execute_lesson_schedule)."""
    messages = []
    if language is None:
        from src.scheduler.memory_helpers import get_user_language
        language = get_user_language(memory_manager, user_id)

    # Compute/use target lesson
    if target_lesson_id is None:
        state = compute_current_lesson_state(memory_manager, user_id)
        target_lesson_id = state["lesson_id"]

    lesson = get_lesson_or_import(db, target_lesson_id)
    if not lesson:
        logger.warning(f"No lesson {target_lesson_id} for user {user_id}")
        return messages

    message = asyncio.run(handler_format_lesson_message(lesson, language))
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return messages

    if not simulate:
        send_outbound_message(db, user, message)
        set_current_lesson(memory_manager, user_id, target_lesson_id)
        user.last_active_at = utc_now()
        db.commit()
        logger.info(f"Delivered lesson {target_lesson_id} to user {user_id}")
    else:
        messages.append(message)

    return messages

