"""Dialogue service subpackages and utilities."""

from src.language.language_service import detect_and_store_language

from src.memories.dialogue_helpers import (
    get_user_language,
)
from src.scheduler.schedule_handlers import handle_schedule_messages
from src.scheduler.schedule_query_handler import build_schedule_status_response

from .command_handlers import (
    handle_gdpr_commands,
    handle_list_memories,
    handle_custom_system_prompt_command,
    parse_custom_prefix,
)
from .ollama_client import call_ollama, stream_ollama
from .pause_handler import detect_pause_request

__all__ = [
    "call_ollama",
    "stream_ollama",
    "get_user_language",
    "detect_and_store_language",
    "detect_pause_request",
    "build_schedule_status_response",
    "handle_custom_system_prompt_command",
    "parse_custom_prefix",
    "handle_list_memories",
    "handle_gdpr_commands",
    "handle_schedule_messages",
]
