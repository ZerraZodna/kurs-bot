"""Dialogue service subpackages and utilities."""

from .ollama_client import call_ollama, stream_ollama
from src.lessons.handler import (
    format_lesson_message,
    translate_text,
)
from src.memories.dialogue_helpers import (
    get_user_language,
    extract_and_store_memories,
)
from src.language.language_service import detect_and_store_language
from .pause_handler import detect_pause_request
from src.scheduler.schedule_query_handler import build_schedule_status_response
from src.scheduler.schedule_handlers import handle_schedule_messages
from src.lessons.advance import maybe_send_next_lesson
from .command_handlers import (
    handle_rag_mode_toggle,
    handle_rag_prompt_command,
    parse_rag_prefix,
    is_rag_mode_enabled,
    handle_forget_commands,
    handle_list_memories,
    handle_gdpr_commands,
)

__all__ = [
    "call_ollama",
    "stream_ollama",
    "format_lesson_message",
    "translate_text",
    "get_user_language",
    "detect_and_store_language",
    "extract_and_store_memories",
    "detect_pause_request",
    "build_schedule_status_response",
    "handle_rag_mode_toggle",
    "handle_rag_prompt_command",
    "parse_rag_prefix",
    "is_rag_mode_enabled",
    "handle_forget_commands",
    "handle_list_memories",
    "handle_gdpr_commands",
    "handle_schedule_messages",
    "maybe_send_next_lesson",
]

