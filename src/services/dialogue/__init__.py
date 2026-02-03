"""Dialogue service subpackages and utilities."""

from .ollama_client import call_ollama
from .lesson_handler import (
    detect_lesson_request,
    handle_lesson_request,
    format_lesson_message,
    translate_text,
)
from .reminder_handler import (
    detect_one_time_reminder,
    get_pending_confirmation,
    resolve_pending_confirmation,
    handle_lesson_confirmation,
)
from .memory_helpers import (
    get_user_language,
    detect_and_store_language,
    extract_and_store_memories,
    delete_user_and_data,
)

__all__ = [
    "call_ollama",
    "detect_lesson_request",
    "handle_lesson_request",
    "format_lesson_message",
    "translate_text",
    "detect_one_time_reminder",
    "get_pending_confirmation",
    "resolve_pending_confirmation",
    "handle_lesson_confirmation",
    "get_user_language",
    "detect_and_store_language",
    "extract_and_store_memories",
    "delete_user_and_data",
]
