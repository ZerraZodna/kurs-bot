"""Compatibility wrappers for scheduler memory helpers.

Canonical implementation lives in `src.scheduler.memory_helpers`.
"""

from src.scheduler.memory_helpers import (
    get_schedule_message,
    get_user_language,
    get_last_sent_lesson_id,
    set_last_sent_lesson_id,
    is_auto_advance_lessons_enabled,
    set_auto_advance_lessons_preference,
    get_pending_confirmation,
    set_pending_confirmation,
)

__all__ = [
    "get_schedule_message",
    "get_user_language",
    "get_last_sent_lesson_id",
    "set_last_sent_lesson_id",
    "is_auto_advance_lessons_enabled",
    "set_auto_advance_lessons_preference",
    "get_pending_confirmation",
    "set_pending_confirmation",
]
