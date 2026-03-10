"""Centralized helpers for lesson state management.

Uses users.lesson for current lesson state and LESSON_COMPLETED memory for completion history.
"""

from typing import Optional, Dict, Any
from datetime import date

from src.memories.manager import MemoryManager
from src.memories.constants import MemoryCategory, MemoryKey
from src.models.user import User


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    s = str(value).strip()
    try:
        return int(s)
    except Exception:
        return None


def get_current_lesson(memory_manager: MemoryManager, user_id: int) -> Optional[Any]:
    """Get current lesson from users.lesson."""
    user = memory_manager.db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return None
    return user.lesson


def set_current_lesson(memory_manager: MemoryManager, user_id: int, lesson: Any) -> None:
    """Set current lesson in users.lesson."""
    user = memory_manager.db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return

    parsed = _parse_int(str(lesson))
    if parsed is None:
        return

    user.lesson = parsed
    memory_manager.db.commit()


def set_next_lesson(memory_manager: MemoryManager, user_id: int, lesson_id: int) -> None:
    """Helper: set the last sent / next lesson id for a user (used by trigger dispatcher)."""
    # Use consolidated lesson_state helper so state stays consistent.
    set_current_lesson(memory_manager, user_id, lesson_id)


def has_lesson_status(memory_manager: MemoryManager, user_id: int) -> bool:
    """Return True when the user has any lesson-related progress info."""
    return get_current_lesson(memory_manager, user_id) is not None


def compute_current_lesson_state(memory_manager: MemoryManager, user_id: int, today: Optional[date] = None) -> Dict[str, Any]:
    """Compute lesson state from users.lesson."""
    lesson_id = get_current_lesson(memory_manager, user_id)

    if lesson_id is None:
        return {
            "lesson_id": 1,
            "progress_note": None,
            "advanced_by_day": True,
            "previous_lesson_id": None,
            "need_confirmation": False,
        }

    return {
        "lesson_id": int(lesson_id),
        "progress_note": None,
        "advanced_by_day": False,
        "previous_lesson_id": None,
        "need_confirmation": False,
    }


def get_lesson_state(memory_manager: MemoryManager, user_id: int) -> Dict[str, Any]:
    """Return lesson state for backward compatibility.
    
    Deprecated: Use get_current_lesson() directly.
    """
    cur = get_current_lesson(memory_manager, user_id)
    return {
        "current_lesson": cur,
        "last_sent_lesson_id": cur,
        "updated_at": None,
    }


def record_lesson_completed(
    memory_manager: MemoryManager,
    user_id: int,
    lesson_id: int,
    source: str = "lesson_system",
    next_lesson: Optional[int] = None,
) -> Dict[str, Any]:
    """Centralized helper to record a completed lesson."""
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        completed = int(lesson_id)
        if not (1 <= completed <= 365):
            raise ValueError(f"Lesson {completed} out of range")
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid lesson_id for completion: {lesson_id}")
        raise
    
    if next_lesson is None:
        next_lesson = min(completed + 1, 365)
    
    memory_manager.store_memory(
        user_id=user_id,
        key=MemoryKey.LESSON_COMPLETED,
        value=str(completed),
        category=MemoryCategory.PROGRESS.value,
        confidence=1.0,
        source=source,
    )
    
    set_current_lesson(memory_manager, user_id, next_lesson)
    
    return {
        "completed_lesson": completed,
        "next_lesson": next_lesson,
        "current_lesson": next_lesson,
    }
