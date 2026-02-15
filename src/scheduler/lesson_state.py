"""Centralized helpers for lesson state management.

Provides a single `lesson_state` JSON memory and convenience accessors for
`current_lesson` and `last_sent_lesson_id`. Backwards-compatible with legacy
`current_lesson` and `last_sent_lesson_id` memories while a migration window
is in effect.
"""

import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from src.memories import MemoryManager


def _latest_memory(memories: list) -> Optional[Dict[str, Any]]:
    if not memories:
        return None
    def _norm(dt):
        if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
            return dt
        return dt.replace(tzinfo=timezone.utc) if dt else datetime.min.replace(tzinfo=timezone.utc)
    return max(memories, key=lambda m: _norm(m.get('created_at')))


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    s = str(value).strip()
    try:
        return int(s)
    except Exception:
        return None


def get_lesson_state(memory_manager: MemoryManager, user_id: int) -> Dict[str, Any]:
    """Return consolidated lesson state for a user.

    Returned dict contains at least the keys `current_lesson` and
    `last_sent_lesson_id` (values may be None). `current_lesson` may be an
    integer, the string "continuing", or None.
    """
    # Try new consolidated memory first
    memories = memory_manager.get_memory(user_id, "lesson_state")
    latest = _latest_memory(memories)
    if latest:
        raw = latest.get("value", "")
        try:
            data = json.loads(raw) if raw else {}
            # normalize fields
            state = {
                "current_lesson": data.get("current_lesson"),
                "last_sent_lesson_id": _parse_int(data.get("last_sent_lesson_id")),
                "updated_at": data.get("updated_at") or latest.get("created_at"),
            }
            return state
        except Exception:
            pass

    # Fallback to legacy memories
    cur_mems = memory_manager.get_memory(user_id, "current_lesson")
    cur = None
    if cur_mems:
        cur_val = cur_mems[0].get("value")
        cur_int = _parse_int(cur_val)
        cur = cur_int if cur_int is not None else str(cur_val)

    last_mems = memory_manager.get_memory(user_id, "last_sent_lesson_id")
    last = None
    if last_mems:
        last = _parse_int(last_mems[0].get("value"))

    return {"current_lesson": cur, "last_sent_lesson_id": last, "updated_at": None}


def set_lesson_state(
    memory_manager: MemoryManager,
    user_id: int,
    current_lesson: Optional[Any] = None,
    last_sent_lesson_id: Optional[int] = None,
    write_legacy: bool = True,
):
    """Write consolidated lesson state and optionally mirror legacy keys.

    Only fields provided (non-None) are updated; others are preserved from
    existing `lesson_state` if present.
    """
    state = get_lesson_state(memory_manager, user_id)
    if current_lesson is not None:
        state["current_lesson"] = current_lesson
    if last_sent_lesson_id is not None:
        state["last_sent_lesson_id"] = int(last_sent_lesson_id)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()

    payload = json.dumps(state)
    memory_manager.store_memory(
        user_id=user_id,
        key="lesson_state",
        value=payload,
        category="progress",
        source="lesson_state_manager",
        allow_duplicates=False,
    )

    # Mirror to legacy keys during migration window for compatibility
    if write_legacy:
        if state.get("current_lesson") is not None:
            val = state.get("current_lesson")
            memory_manager.store_memory(
                user_id=user_id,
                key="current_lesson",
                value=str(val),
                category="progress",
                source="lesson_state_manager",
                allow_duplicates=False,
            )
        if state.get("last_sent_lesson_id") is not None:
            memory_manager.store_memory(
                user_id=user_id,
                key="last_sent_lesson_id",
                value=str(state.get("last_sent_lesson_id")),
                category="progress",
                source="lesson_state_manager",
                allow_duplicates=False,
            )


def get_current_lesson(memory_manager: MemoryManager, user_id: int) -> Optional[Any]:
    return get_lesson_state(memory_manager, user_id).get("current_lesson")


def set_current_lesson(memory_manager: MemoryManager, user_id: int, lesson: Any, write_legacy: bool = True) -> None:
    set_lesson_state(memory_manager, user_id, current_lesson=lesson, write_legacy=write_legacy)


def get_last_sent_lesson_id(memory_manager: MemoryManager, user_id: int) -> Optional[int]:
    return get_lesson_state(memory_manager, user_id).get("last_sent_lesson_id")


def set_last_sent_lesson_id(memory_manager: MemoryManager, user_id: int, lesson_id: int, write_legacy: bool = True) -> None:
    set_lesson_state(memory_manager, user_id, last_sent_lesson_id=lesson_id, write_legacy=write_legacy)
