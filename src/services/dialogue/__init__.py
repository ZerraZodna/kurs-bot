"""Dialogue service subpackages and utilities."""

from .ollama_client import call_ollama
from .lesson_handler import (
    detect_lesson_request,
    handle_lesson_request,
    format_lesson_message,
    translate_text,
)
from .reminder_handler import (
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
from .pause_handler import detect_pause_request
from .schedule_query_handler import detect_schedule_status_request, build_schedule_status_response
from .schedule_handlers import handle_schedule_messages
from .lesson_advance import maybe_send_next_lesson
from .command_handlers import (
    handle_rag_mode_toggle,
    handle_rag_prompt_command,
    parse_rag_prefix,
    is_rag_mode_enabled,
    handle_forget_commands,
    handle_schedule_deletion_commands,
    handle_list_memories,
    handle_gdpr_commands,
    handle_debug_next_day,
)

__all__ = [
    "call_ollama",
    "detect_lesson_request",
    "handle_lesson_request",
    "format_lesson_message",
    "translate_text",
    "get_pending_confirmation",
    "resolve_pending_confirmation",
    "handle_lesson_confirmation",
    "get_user_language",
    "detect_and_store_language",
    "extract_and_store_memories",
    "delete_user_and_data",
    "detect_pause_request",
    "detect_schedule_status_request",
    "build_schedule_status_response",
    "handle_rag_mode_toggle",
    "handle_rag_prompt_command",
    "parse_rag_prefix",
    "is_rag_mode_enabled",
    "handle_forget_commands",
    "handle_schedule_deletion_commands",
    "handle_list_memories",
    "handle_gdpr_commands",
    "handle_debug_next_day",
    "handle_schedule_messages",
    "maybe_send_next_lesson",
]
