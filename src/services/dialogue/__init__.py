"""Dialogue service subpackages and utilities."""

from src.language.language_service import detect_and_store_language
from src.lessons.advance import maybe_send_next_lesson
from src.lessons.handler import (
    format_lesson_message,
    translate_text,
)
from src.memories.dialogue_helpers import (
    get_user_language,
)
from src.scheduler.schedule_handlers import handle_schedule_messages
from src.scheduler.schedule_query_handler import build_schedule_status_response

from .command_handlers import (
    handle_gdpr_commands,
    handle_list_memories,
    handle_rag_prompt_command,
    parse_rag_prefix,
)
from .ollama_client import call_ollama, stream_ollama
from .pause_handler import detect_pause_request

__all__ = [
    "call_ollama",
    "stream_ollama",
    "format_lesson_message",
    "translate_text",
    "get_user_language",
    "detect_and_store_language",
    "detect_pause_request",
    "build_schedule_status_response",
    "handle_rag_prompt_command",
    "parse_rag_prefix",
    "handle_list_memories",
    "handle_gdpr_commands",
    "handle_schedule_messages",
    "maybe_send_next_lesson",
]
