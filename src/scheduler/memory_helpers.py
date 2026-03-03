"""Memory helpers for scheduler."""

import json
from datetime import datetime, timezone
from typing import Optional

from src.memories.constants import MemoryCategory, MemoryKey
from src.memories.manager import MemoryManager
from src.lessons.state import (
    get_last_sent_lesson_id as _get_last_sent_lesson_id,
    set_last_sent_lesson_id as _set_last_sent_lesson_id,
)
from src.core.timezone import to_utc


def get_schedule_message(memory_manager: MemoryManager, user_id: int, schedule_id: int) -> Optional[str]:
    memories = memory_manager.get_memory(user_id=user_id, key=MemoryKey.SCHEDULE_MESSAGE)
    for memory in memories:
        try:
            data = json.loads(memory.get("value", ""))
            if data.get("schedule_id") == schedule_id:
                return data.get("message")
        except Exception:
            continue
    return None


def get_user_language(memory_manager: MemoryManager, user_id: int) -> str:
    memories = memory_manager.get_memory(user_id, MemoryKey.USER_LANGUAGE)
    return memories[0].get("value", "en") if memories else "en"


def get_last_sent_lesson_id(memory_manager: MemoryManager, user_id: int) -> Optional[int]:
    """Wrapper: use consolidated lesson_state getter."""
    return _get_last_sent_lesson_id(memory_manager, user_id)


def set_last_sent_lesson_id(memory_manager: MemoryManager, user_id: int, lesson_id: int) -> None:
    """Wrapper: use consolidated lesson_state setter."""
    _set_last_sent_lesson_id(memory_manager, user_id, lesson_id, write_legacy=True)


def is_auto_advance_lessons_enabled(memory_manager: MemoryManager, user_id: int) -> bool:
    memories = memory_manager.get_memory(user_id, MemoryKey.AUTO_ADVANCE_LESSONS)
    if not memories:
        return False
    value = str(memories[0].get("value", "")).strip().lower()
    return value in {"true", "1", "yes", "on", "enabled"}


def set_auto_advance_lessons_preference(
    memory_manager: MemoryManager,
    user_id: int,
    enabled: bool,
    source: str = "dialogue_engine",
) -> None:
    memory_manager.store_memory(
        user_id=user_id,
        key=MemoryKey.AUTO_ADVANCE_LESSONS,
        value="true" if enabled else "false",
        category=MemoryCategory.PREFERENCE.value,
        confidence=1.0,
        source=source,
    )


def get_pending_confirmation(memory_manager: MemoryManager, user_id: int) -> Optional[dict]:
    memories = memory_manager.get_memory(user_id, MemoryKey.LESSON_CONFIRMATION_PENDING)
    if not memories:
        return None

    def _normalize_dt(value: Optional[datetime]) -> datetime:
        if isinstance(value, datetime):
            return to_utc(value)
        # Use datetime module from outer scope - avoid local variable shadowing
        from datetime import datetime as _dt
        return to_utc(_dt.min)

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
        key=MemoryKey.LESSON_CONFIRMATION_PENDING,
        value=payload,
        category=MemoryCategory.CONVERSATION.value,
        ttl_hours=24,
        source="scheduler",
    )
