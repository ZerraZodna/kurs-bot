"""Centralized helpers for lesson state management.

Uses users.lesson for current lesson state memory for completion history.
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


def set_current_lesson(memory_manager: MemoryManager, user_id: int, lesson: Any, refresh: bool = False) -> None:
    """Set current lesson in users.lesson."""
    user = memory_manager.db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return

    parsed = _parse_int(str(lesson))
    if parsed is None:
        return

    user.lesson = parsed
    memory_manager.db.commit()
    if refresh:
        memory_manager.db.refresh(user)


def has_lesson_status(memory_manager: MemoryManager, user_id: int) -> bool:
    """Return True when the user has any lesson-related progress info."""
    return get_current_lesson(memory_manager, user_id) is not None


def compute_current_lesson_state(memory_manager: MemoryManager, user_id: int, today: Optional[date] = None) -> Dict[str, Any]:
    """Compute lesson state from users.lesson and last_active_at for daily advancement."""
    from datetime import date, datetime, timezone
    from src.models.user import User
    
    lesson_id = get_current_lesson(memory_manager, user_id)

    if lesson_id is None:
        return {
            "lesson_id": 1,
            "progress_note": None,
            "advanced_by_day": True,
            "previous_lesson_id": None
        }

    user = memory_manager.db.query(User).filter(User.user_id == user_id).first()
    last_active = getattr(user, 'last_active_at', None)
    
    # Use UTC-aware today by default
    if today is None:
        today = datetime.now(timezone.utc).date()
    today_date = today
    
    if last_active and last_active.date() < today_date:
        previous_id = lesson_id
        proposed_id = min(int(lesson_id) + 1, 365)
        return {
            "lesson_id": proposed_id,
            "progress_note": None,
            "advanced_by_day": True,
            "previous_lesson_id": previous_id
        }

    return {
        "lesson_id": int(lesson_id),
        "progress_note": None,
        "advanced_by_day": False,
        "previous_lesson_id": None
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
