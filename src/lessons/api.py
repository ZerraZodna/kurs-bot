"""Public API facade for lesson operations.

This module provides a unified public API for all lesson-related operations.
Other modules should import from here rather than directly from internal
lesson modules.
"""

import logging
from typing import Optional, Dict, Any
from datetime import date

from sqlalchemy.orm import Session

from src.models.database import Lesson
from src.memories.manager import MemoryManager

# Import from internal modules
from src.lessons.state import (
    get_current_lesson as _get_current_lesson,
    set_current_lesson as _set_current_lesson,
    has_lesson_status as _has_lesson_status,
    compute_current_lesson_state as _compute_current_lesson_state,
)
from src.lessons.handler import (
    format_lesson_message as _format_lesson_message,
    _find_lesson_by_id as _find_lesson,
)
from src.lessons.advance import maybe_send_next_lesson as _maybe_send_next_lesson

logger = logging.getLogger(__name__)


def get_lesson(lesson_id: int, session: Session) -> Optional[Lesson]:
    """Retrieve a lesson by ID."""
    return _find_lesson(session, lesson_id)


def format_lesson_message(lesson: Lesson, language: Optional[str] = None) -> str:
    """Format a lesson for display."""
    import asyncio
    try:
        return asyncio.run(_format_lesson_message(lesson, language))
    except Exception as e:
        logger.warning(f"Failed to format lesson message: {e}")
        return f"Lesson {lesson.lesson_id}: {lesson.title}\n\n{lesson.content}"


async def maybe_send_next_lesson(
    user_id: int,
    text: str,
    session: Session,
    prompt_builder: Any,
    memory_manager: MemoryManager,
    call_ollama: Any,
) -> Optional[str]:
    """Check if we should auto-send the next lesson on a new day."""
    return await _maybe_send_next_lesson(
        user_id=user_id,
        text=text,
        session=session,
        prompt_builder=prompt_builder,
        memory_manager=memory_manager,
        call_ollama=call_ollama,
    )


# Re-export state functions
def get_current_lesson(memory_manager: MemoryManager, user_id: int) -> Optional[Any]:
    """Get the user's current lesson."""
    return _get_current_lesson(memory_manager, user_id)


def set_current_lesson(memory_manager: MemoryManager, user_id: int, lesson: Any) -> None:
    """Set the user's current lesson."""
    _set_current_lesson(memory_manager, user_id, lesson)


def has_lesson_status(memory_manager: MemoryManager, user_id: int) -> bool:
    """Check if user has lesson status."""
    return _has_lesson_status(memory_manager, user_id)


def compute_current_lesson_state(memory_manager: MemoryManager, user_id: int, today: Optional[date] = None) -> Dict[str, Any]:
    """Compute current lesson state."""
    return _compute_current_lesson_state(memory_manager, user_id, today)


# Re-export types for convenience
__all__ = [
    "get_lesson",
    "format_lesson_message",
    "get_current_lesson",
    "set_current_lesson",
    "has_lesson_status",
    "compute_current_lesson_state",
    "maybe_send_next_lesson",
]

