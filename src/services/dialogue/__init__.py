"""Dialogue service subpackages and utilities."""

from src.config import settings
from src.language.language_service import detect_and_store_language

from src.memories.dialogue_helpers import (
    get_user_language,
)
from src.scheduler.schedule_handlers import handle_schedule_messages
from src.scheduler.schedule_query_handler import build_schedule_status_response

from .command_handlers import (
    handle_gdpr_commands,
    handle_list_memories,
    handle_list_schedules,
    handle_custom_system_prompt_command,
    parse_custom_prefix,
)
from .ollama_client import call_ollama, stream_ollama
from .openai_client import call_llm, stream_llm
from .pause_handler import detect_pause_request


async def call_llm_router(
    prompt: str,
    model: str | None = None,
    language: str | None = None,
    temperature: float | None = None,
) -> str:
    """Unified LLM call that routes to the configured provider.

    Respects ``settings.LLM_PROVIDER`` ("ollama" or "openai") so callers
    don't need to check it themselves.
    """
    if settings.LLM_PROVIDER == "openai":
        return await call_llm(prompt, model=model, language=language, temperature=temperature)
    return await call_ollama(prompt, model=model, language=language, temperature=temperature)


__all__ = [
    "call_ollama",
    "stream_ollama",
    "call_llm",
    "stream_llm",
    "call_llm_router",
    "get_user_language",
    "detect_and_store_language",
    "detect_pause_request",
    "build_schedule_status_response",
    "handle_custom_system_prompt_command",
    "parse_custom_prefix",
    "handle_list_memories",
    "handle_list_schedules",
    "handle_gdpr_commands",
    "handle_schedule_messages",
]
