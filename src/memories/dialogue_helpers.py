"""Memory extraction and user utilities."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from src.memories.manager import MemoryManager
from src.memories.ai_judge import MemoryJudge
from src.memories.constants import MemoryCategory, MemoryKey
from src.config import settings
from src.lessons.state import set_current_lesson

logger = logging.getLogger(__name__)


def _normalize_lesson_completed_value(value) -> str | None:
    """Return a normalized lesson id string (1-365) or None for invalid input."""
    try:
        if isinstance(value, int):
            lesson_id = value
        elif isinstance(value, float):
            if not value.is_integer():
                return None
            lesson_id = int(value)
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            if raw.isdigit():
                lesson_id = int(raw)
            else:
                m = re.search(r"\b(?:lesson|leksjon)?\s*(\d{1,3})\b", raw.lower())
                if not m:
                    return None
                lesson_id = int(m.group(1))
        else:
            return None
    except Exception:
        return None

    if 1 <= int(lesson_id) <= 365:
        return str(int(lesson_id))
    return None

def get_user_language(memory_manager: MemoryManager, user_id: int) -> str:
    #"""Get user's preferred language."""
    memories = memory_manager.get_memory(user_id, MemoryKey.USER_LANGUAGE)
    ## Stored values are ISO codes (e.g., 'en', 'no'). Return stored value or 'en'.
    return memories[0].get("value", "en") if memories else "en"



async def extract_and_store_memories(
    memory_manager: MemoryManager,
    memory_judge: MemoryJudge,
    user_id: int,
    user_message: str,
    rag_mode: bool = False,
) -> None:
    """
    Extract and store memories from user message.

    Args:
        memory_manager: Memory manager instance
        memory_judge: Memory judge instance
        user_id: User ID
        user_message: The user's message
    """
    try:
        existing_memories = {}
        for key in [
            MemoryKey.FIRST_NAME,
            MemoryKey.ACIM_COMMITMENT,
            MemoryKey.LEARNING_GOAL,
        ]:
            memories = memory_manager.get_memory(user_id, key)
            if memories:
                existing_memories[key] = memories[0].get("value")

        user_context = (
            {"user_id": user_id, "existing_memories": existing_memories}
            if existing_memories
            else None
        )

        # Determine user language from stored preference (fallback to English)
        user_lang = get_user_language(memory_manager, user_id)

        # Use MemoryJudge to extract memories
        extracted_memories = await memory_judge.extract_and_judge_memories(
            user_message, user_context, language=user_lang
        )

        logger.debug(f"user_id={user_id} user_message={user_message!r} extracted={extracted_memories}")

        for memory in extracted_memories:
            try:
                key = memory.get("key")
                val = memory.get("value")
                # Route lesson state writes through the centralized helper
                if key == MemoryKey.CURRENT_LESSON:
                    # Normalize numeric lesson values to int, keep strings like 'continuing'
                    parsed = None
                    try:
                        parsed = int(val)
                    except Exception:
                        parsed = val
                    set_current_lesson(memory_manager, user_id, parsed)
                elif key == MemoryKey.LESSON_COMPLETED:
                    normalized = _normalize_lesson_completed_value(val)
                    if normalized is None:
                        logger.info(
                            "Skipping invalid lesson_completed memory for user %s: %r",
                            user_id,
                            val,
                        )
                        continue
                    # Use centralized helper for DRY
                    from src.lessons.state import record_lesson_completed
                    record_lesson_completed(
                        memory_manager,
                        user_id,
                        int(normalized),
                        source="dialogue_engine_extractor",
                    )
                else:
                    # Store the memory
                    memory_manager.store_memory(
                        user_id=user_id,
                        key=key,
                        value=val,
                        confidence=memory.get("confidence", 1.0),
                        ttl_hours=memory.get("ttl_hours"),
                        source="dialogue_engine_extractor",
                    )
                sval = str(val) if val is not None else ''
                logger.debug(f"Memory saved: user={user_id} key={memory.get('key')} value={sval[:50]}")
            except Exception as e:
                logger.error(f"Error storing memory: {e}")

    except Exception as e:
        logger.error(f"Error in memory extraction: {e}")
