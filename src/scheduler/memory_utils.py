"""Memory helpers for scheduler."""

import json
from datetime import datetime, timezone
from src.services.timezone_utils import to_utc
from typing import Optional
from src.scheduler.lesson_state import get_last_sent_lesson_id as _get_last_sent_lesson_id, set_last_sent_lesson_id as _set_last_sent_lesson_id

from src.memories import MemoryManager

def get_schedule_message(memory_manager: MemoryManager, user_id: int, schedule_id: int) -> Optional[str]:
    memories = memory_manager.get_memory(user_id=user_id, key="schedule_message")
    for memory in memories:
        try:
            data = json.loads(memory.get("value", ""))
            if data.get("schedule_id") == schedule_id:
                return data.get("message")
        except Exception:
            continue
    return None

def get_user_language(memory_manager: MemoryManager, user_id: int) -> str:
    return "en"
    #memories = memory_manager.get_memory(user_id, "user_language")
    #return memories[0].get("value", "en") if memories else "en"

def get_last_sent_lesson_id(memory_manager: MemoryManager, user_id: int) -> Optional[int]:
    """Wrapper: use consolidated lesson_state getter."""
    return _get_last_sent_lesson_id(memory_manager, user_id)

def set_last_sent_lesson_id(memory_manager: MemoryManager, user_id: int, lesson_id: int) -> None:
    """Wrapper: use consolidated lesson_state setter."""
    _set_last_sent_lesson_id(memory_manager, user_id, lesson_id, write_legacy=True)

def get_pending_confirmation(memory_manager: MemoryManager, user_id: int) -> Optional[dict]:
    memories = memory_manager.get_memory(user_id, "lesson_confirmation_pending")
    if not memories:
        return None

    def _normalize_dt(value: Optional[datetime]) -> datetime:
        if isinstance(value, datetime):
            return to_utc(value)
        return to_utc(datetime.min)

    latest = max(memories, key=lambda m: _normalize_dt(m.get("created_at")))
    raw = latest.get("value", "")
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("lesson_id"):
            return data
    except Exception:
        return None
    return None

def set_pending_confirmation(
    memory_manager: MemoryManager,
    user_id: int,
    lesson_id: int,
    next_lesson_id: int,
) -> None:
    payload = json.dumps({"lesson_id": lesson_id, "next_lesson_id": next_lesson_id})
    memory_manager.store_memory(
        user_id=user_id,
        key="lesson_confirmation_pending",
        value=payload,
        category="conversation",
        ttl_hours=24,
        source="scheduler",
    )