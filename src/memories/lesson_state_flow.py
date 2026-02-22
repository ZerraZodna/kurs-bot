"""Centralized lesson-state decision helpers.

These helpers consolidate how we decide whether to auto-send a lesson,
ask for confirmation, or wait, and how we update lesson memories when
the user reports progress.
"""

from __future__ import annotations

from datetime import datetime, date, timezone, timedelta
from typing import Any, Dict, Optional

from src.memories.constants import MemoryCategory, MemoryKey
from src.memories.lesson_state import (
    compute_current_lesson_state,
    get_lesson_state,
    set_current_lesson,
    set_last_sent_lesson_id,
)
from src.memories.manager import MemoryManager


def _parse_updated_at(updated_at: Any) -> Optional[datetime]:
    """Best-effort parse of the lesson_state updated_at value."""
    if updated_at is None:
        return None
    if isinstance(updated_at, datetime):
        return updated_at if updated_at.tzinfo else updated_at.replace(tzinfo=timezone.utc)
    if isinstance(updated_at, str):
        try:
            dt = datetime.fromisoformat(updated_at)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _gap_days(updated_at: Optional[datetime], today: date) -> int:
    if not updated_at:
        return 0
    return max((today - updated_at.date()).days, 0)


def determine_lesson_action(
    memory_manager: MemoryManager,
    user_id: int,
    *,
    today: Optional[date] = None,
    max_gap_without_confirmation: int = 1,
) -> Dict[str, Any]:
    """Compute the next lesson action for a user.

    Returns a dict with keys:
    - action: "send" | "confirm" | "wait"
    - lesson_id: proposed lesson to send (if action == send)
    - next_lesson_id: next lesson after the confirmation target (if confirm)
    - confirmation_lesson_id: lesson we want confirmation about (if confirm)
    - previous_lesson_id, need_confirmation, advanced_by_day, gap_days, reason
    """
    today = today or datetime.now(timezone.utc).date()
    state = compute_current_lesson_state(memory_manager, user_id, today=today)
    raw_state = get_lesson_state(memory_manager, user_id)

    lesson_id = state.get("lesson_id")
    previous_lesson_id = state.get("previous_lesson_id")
    advanced_by_day = bool(state.get("advanced_by_day"))
    need_confirmation_flag = bool(state.get("need_confirmation"))

    updated_at = _parse_updated_at(raw_state.get("updated_at"))
    gap = _gap_days(updated_at, today)

    # Default response skeleton
    result = {
        "state": state,
        "action": "wait",
        "lesson_id": lesson_id,
        "previous_lesson_id": previous_lesson_id,
        "next_lesson_id": None,
        "confirmation_lesson_id": None,
        "need_confirmation": need_confirmation_flag,
        "advanced_by_day": advanced_by_day,
        "gap_days": gap,
        "reason": None,
    }

    # Case 1: explicit current_lesson without last_sent
    if need_confirmation_flag and lesson_id:
        result.update(
            {
                "action": "confirm",
                "confirmation_lesson_id": lesson_id,
                "next_lesson_id": min(lesson_id + 1, 365),
                "reason": "explicit_current_without_last_sent",
            }
        )
        return result

    # Case 2: gap larger than allowed — ask user before advancing
    if advanced_by_day and gap > max_gap_without_confirmation:
        confirm_lesson = previous_lesson_id or max((lesson_id or 2) - 1, 1)
        next_lesson_id = lesson_id
        result.update(
            {
                "action": "confirm",
                "confirmation_lesson_id": confirm_lesson,
                "next_lesson_id": next_lesson_id,
                "reason": "multi_day_gap",
            }
        )
        return result

    # Case 3: normal daily advance
    if advanced_by_day and lesson_id:
        result.update({"action": "send", "reason": "auto_advance"})
        return result

    # Case 4: no advance needed, wait
    result["reason"] = "no_advance"
    return result


def apply_reported_progress(
    memory_manager: MemoryManager, user_id: int, reported_current_lesson: int
) -> Dict[str, Any]:
    """Update lesson state based on a user reporting their current lesson.

    Returns a dict with keys: current_lesson, completed_lesson.
    """
    if not reported_current_lesson or reported_current_lesson < 1:
        return {"current_lesson": None, "completed_lesson": None}

    current = min(int(reported_current_lesson), 365)
    completed = max(current - 1, 1)

    memory_manager.store_memory(
        user_id=user_id,
        key=MemoryKey.LESSON_COMPLETED,
        value=str(completed),
        category=MemoryCategory.PROGRESS.value,
        confidence=1.0,
        source="lesson_state_flow",
    )
    set_current_lesson(memory_manager, user_id, current)
    set_last_sent_lesson_id(memory_manager, user_id, current)

    return {"current_lesson": current, "completed_lesson": completed}
