"""Lesson domain package: handlers, state, and progression logic."""

from .advance import is_simple_greeting, maybe_send_next_lesson
from .handler import (
    format_lesson_message,
    translate_text,
)
from .importer import ensure_lessons_available
from .state import (
    compute_current_lesson_state,
    get_current_lesson,
    get_lesson_state,
    has_lesson_status,
    set_current_lesson,
    set_next_lesson,
)
from .state_flow import apply_reported_progress, determine_lesson_action

__all__ = [
    "is_simple_greeting",
    "maybe_send_next_lesson",
    "format_lesson_message",
    "translate_text",
    "ensure_lessons_available",
    "compute_current_lesson_state",
    "get_current_lesson",
    "get_lesson_state",
    "has_lesson_status",
    "set_current_lesson",
    "set_next_lesson",
    "apply_reported_progress",
    "determine_lesson_action",
]

