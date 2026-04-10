"""Public API facade for lesson operations.

This module provides a unified public API for all lesson-related operations.
Other modules should import from here rather than directly from internal
lesson modules.
"""

import logging
from datetime import date
from typing import Any, Dict

from sqlalchemy.orm import Session

from src.lessons.handler import (
    _find_lesson_by_id as _find_lesson,
)
from src.lessons.handler import (
    format_lesson_message as _format_lesson_message,
)
from src.lessons.state import (
    compute_current_lesson_state as _compute_current_lesson_state,
)

# Import from internal modules
from src.lessons.state import (
    get_current_lesson as _get_current_lesson,
)
from src.lessons.state import (
    has_lesson_status as _has_lesson_status,
)
from src.lessons.state import (
    set_current_lesson as _set_current_lesson,
)
from src.memories.manager import MemoryManager
from src.models.database import Lesson

logger = logging.getLogger(__name__)


def get_lesson(lesson_id: int, session: Session) -> Lesson | None:
    """Retrieve a lesson by ID."""
    return _find_lesson(session, lesson_id)


def format_lesson_message(lesson: Lesson, language: str | None = None) -> str:
    """Format a lesson for display."""
    import asyncio

    try:
        return asyncio.run(_format_lesson_message(lesson, language))
    except Exception as e:
        logger.warning(f"Failed to format lesson message: {e}")
        return f"Lesson {lesson.lesson_id}: {lesson.title}\n\n{lesson.content}"


# Re-export state functions
def get_current_lesson(memory_manager: MemoryManager, user_id: int) -> Any | None:
    """Get the user's current lesson."""
    return _get_current_lesson(memory_manager, user_id)


def set_current_lesson(memory_manager: MemoryManager, user_id: int, lesson: Any) -> None:
    """Set the user's current lesson."""
    _set_current_lesson(memory_manager, user_id, lesson)


def has_lesson_status(memory_manager: MemoryManager, user_id: int) -> bool:
    """Check if user has lesson status."""
    return _has_lesson_status(memory_manager, user_id)


def compute_current_lesson_state(
    memory_manager: MemoryManager, user_id: int, today: date | None = None
) -> Dict[str, Any]:
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
]
