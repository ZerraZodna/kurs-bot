"""Centralized helpers for lesson state management.

Uses LESSON_CURRENT and LESSON_COMPLETED memory entries for lesson state.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any

from src.memories.manager import MemoryManager
from src.memories.constants import MemoryCategory, MemoryKey
from datetime import date


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    s = str(value).strip()
    try:
        return int(s)
    except Exception:
        return None


def get_current_lesson(memory_manager: MemoryManager, user_id: int) -> Optional[Any]:
    """Get current lesson from LESSON_CURRENT memory."""
    memories = memory_manager.get_memory(user_id, MemoryKey.LESSON_CURRENT)
    if memories:
        val = memories[0].get("value")
        try:
            return int(val)
        except (ValueError, TypeError):
            return val
    return None


def set_current_lesson(memory_manager: MemoryManager, user_id: int, lesson: Any) -> None:
    """Set current lesson using LESSON_CURRENT memory."""
    memory_manager.store_memory(
        user_id=user_id,
        key=MemoryKey.LESSON_CURRENT,
        value=str(lesson),
        category=MemoryCategory.PROGRESS.value,
        source="lesson_state_manager",
        allow_duplicates=False,
    )


def set_next_lesson(memory_manager: MemoryManager, user_id: int, lesson_id: int) -> None:
    """Helper: set the last sent / next lesson id for a user (used by trigger dispatcher)."""
    # Use consolidated lesson_state helper so state stays consistent.
    set_current_lesson(memory_manager, user_id, lesson_id)


def has_lesson_status(memory_manager: MemoryManager, user_id: int) -> bool:
    """Return True when the user has any lesson-related progress info."""
    return get_current_lesson(memory_manager, user_id) is not None


def compute_current_lesson_state(memory_manager: MemoryManager, user_id: int, today: Optional[date] = None) -> Dict[str, Any]:
    """Compute the lesson state used for determining "today's" lesson.
    
    Returns:
        - lesson_id: The current/next lesson ID to send
        - advanced_by_day: True if we should advance to next lesson (new day since last lesson)
        - previous_lesson_id: The lesson that was previously sent
        - need_confirmation: True if we need user confirmation before advancing
    """
    if today is None:
        today = datetime.now(timezone.utc).date()

    # Get the LESSON_CURRENT memory to check when it was created
    memories = memory_manager.get_memory(user_id, MemoryKey.LESSON_CURRENT)
    
    # If no current lesson, start with lesson 1
    if not memories:
        return {
            "lesson_id": 1, 
            "progress_note": None, 
            "advanced_by_day": True,  # New user, can start with lesson 1
            "previous_lesson_id": None, 
            "need_confirmation": False
        }

    # Get the most recent LESSON_CURRENT memory
    current_memory = memories[0]
    cur = current_memory.get("value")
    created_at = current_memory.get("created_at")
    
    if cur is None:
        return {
            "lesson_id": 1, 
            "progress_note": None, 
            "advanced_by_day": True, 
            "previous_lesson_id": None, 
            "need_confirmation": False
        }

    if str(cur).isdigit():
        lesson_id = int(cur)
        # Note: need_confirmation is NOT used for lesson progression anymore.
        # It's only used for GDPR-related confirmations (e.g., during onboarding or GDPR delete requests).
        
        # Check if the lesson was already sent today
        if created_at:
            # Convert created_at to date for comparison
            if isinstance(created_at, datetime):
                created_date = created_at.date()
            else:
                # Handle string format if needed
                created_date = created_at
            
            # If created today, don't advance (lesson already sent)
            if created_date == today:
                return {
                    "lesson_id": lesson_id,
                    "progress_note": None,
                    "advanced_by_day": False,  # Already sent today
                    "previous_lesson_id": None,
                    "need_confirmation": False
                }
            else:
                # Created before today - it's a new day, advance to next lesson
                previous_lesson_id = lesson_id
                next_lesson_id = (lesson_id % 365) + 1
                return {
                    "lesson_id": next_lesson_id,
                    "progress_note": None,
                    "advanced_by_day": True,  # New day, advance
                    "previous_lesson_id": previous_lesson_id,
                    "need_confirmation": False
                }
        else:
            # No created_at - assume it's a new day
            return {
                "lesson_id": lesson_id,
                "progress_note": None,
                "advanced_by_day": False,
                "previous_lesson_id": None,
                "need_confirmation": False
            }

    return {"lesson_id": 1, "progress_note": None, "advanced_by_day": False, "previous_lesson_id": None, "need_confirmation": False}


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
