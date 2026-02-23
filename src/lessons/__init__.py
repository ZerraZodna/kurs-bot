"""Lesson domain package: handlers, state, and progression logic."""

from .advance import is_simple_greeting, maybe_send_next_lesson
from .handler import (
    detect_lesson_request,
    format_lesson_message,
    handle_lesson_request,
    pre_llm_lesson_short_circuit,
    process_lesson_query,
    translate_text,
)
from .importer import ensure_lessons_available
from .state import (
    compute_current_lesson_state,
    get_current_lesson,
    get_last_sent_lesson_id,
    get_lesson_state,
    has_lesson_status,
    set_current_lesson,
    set_last_sent_lesson_id,
    set_lesson_state,
)
from .state_flow import apply_reported_progress, determine_lesson_action

__all__ = [
    "is_simple_greeting",
    "maybe_send_next_lesson",
    "detect_lesson_request",
    "format_lesson_message",
    "handle_lesson_request",
    "pre_llm_lesson_short_circuit",
    "process_lesson_query",
    "translate_text",
    "ensure_lessons_available",
    "compute_current_lesson_state",
    "get_current_lesson",
    "get_last_sent_lesson_id",
    "get_lesson_state",
    "has_lesson_status",
    "set_current_lesson",
    "set_last_sent_lesson_id",
    "set_lesson_state",
    "apply_reported_progress",
    "determine_lesson_action",
]
