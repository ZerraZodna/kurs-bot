"""Centralized helpers for lesson state management.

Provides a single `lesson_state` JSON memory and convenience accessors for
`current_lesson` and `last_sent_lesson_id`. Backwards-compatible with legacy
`current_lesson` and `last_sent_lesson_id` memories while a migration window
is in effect.
"""

import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from src.memories.manager import MemoryManager
from datetime import date


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

def get_current_lesson(memory_manager: MemoryManager, user_id: int) -> Optional[Any]:
    return get_lesson_state(memory_manager, user_id).get("current_lesson")


def set_current_lesson(memory_manager: MemoryManager, user_id: int, lesson: Any, write_legacy: bool = True) -> None:
    set_lesson_state(memory_manager, user_id, current_lesson=lesson, write_legacy=write_legacy)


def get_last_sent_lesson_id(memory_manager: MemoryManager, user_id: int) -> Optional[int]:
    return get_lesson_state(memory_manager, user_id).get("last_sent_lesson_id")


def set_last_sent_lesson_id(memory_manager: MemoryManager, user_id: int, lesson_id: int, write_legacy: bool = True) -> None:
    set_lesson_state(memory_manager, user_id, last_sent_lesson_id=lesson_id, write_legacy=write_legacy)


def has_lesson_status(memory_manager: MemoryManager, user_id: int) -> bool:
    """Return True when the user has any lesson-related progress info.

    This central helper makes onboarding and other callers clearer and
    keeps the logic in one place for future changes.
    """
    state = get_lesson_state(memory_manager, user_id)
    return state.get("current_lesson") is not None or state.get("last_sent_lesson_id") is not None


def compute_current_lesson_state(memory_manager: MemoryManager, user_id: int, today: Optional[date] = None) -> Dict[str, Any]:
    """Compute the lesson state used for determining "today's" lesson.

    Returns same shape as PromptBuilder._get_current_lesson_state expects:
    {"lesson_id": int, "progress_note": Optional[str], "advanced_by_day": bool, "previous_lesson_id": Optional[int], "need_confirmation": bool}

    `today` may be provided (date) to allow deterministic testing; if None,
    uses UTC today.
    """
    if today is None:
        today = datetime.now(timezone.utc).date()

    state = get_lesson_state(memory_manager, user_id)
    cur = state.get("current_lesson")
    last_sent = state.get("last_sent_lesson_id")
    updated_at = state.get("updated_at")

    # If user explicitly set a current_lesson (numeric), honor it.
    try:
        if cur is not None and str(cur).isdigit():
            # If we have a numeric current_lesson but no recorded last_sent
            # lesson, surface that we need a confirmation before delivering
            # the lesson (e.g., user onboarding reported "I'm on lesson 8").
            if last_sent is None:
                return {"lesson_id": int(cur), "progress_note": None, "advanced_by_day": False, "previous_lesson_id": None, "need_confirmation": True}
            return {"lesson_id": int(cur), "progress_note": None, "advanced_by_day": False, "previous_lesson_id": None, "need_confirmation": False}
    except Exception:
        pass

    # If we have a last_sent value, decide whether to advance by day.
    if last_sent is not None:
        try:
            if updated_at:
                updated_dt = datetime.fromisoformat(updated_at) if isinstance(updated_at, str) else updated_at
            else:
                updated_dt = datetime.now(timezone.utc)
            last_date = updated_dt.date()
            if last_date < today:
                next_id = last_sent + 1 if last_sent < 365 else 365
                note = (
                    f"The user received Lesson {last_sent} on a previous day. "
                    f"Assume today's lesson is Lesson {next_id}."
                )
                return {"lesson_id": next_id, "progress_note": note, "advanced_by_day": True, "previous_lesson_id": last_sent, "need_confirmation": False}
            return {"lesson_id": last_sent, "progress_note": None, "advanced_by_day": False, "previous_lesson_id": None, "need_confirmation": False}
        except Exception:
            pass

    # Fallback to Lesson 1 when nothing else is known
    return {"lesson_id": 1, "progress_note": None, "advanced_by_day": False, "previous_lesson_id": None, "need_confirmation": False}
