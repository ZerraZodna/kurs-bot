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
from src.models.database import Memory

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


def _get_all_existing_memories(memory_manager: MemoryManager, user_id: int) -> list:
    """Get all active memories for a user for conflict detection."""
    try:
        from src.models.database import SessionLocal
        db = SessionLocal()
        try:
            memories = (
                db.query(Memory)
                .filter(Memory.user_id == user_id, Memory.is_active == True)
                .all()
            )
            return memories
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to get all existing memories: {e}")
        return []


async def extract_and_store_memories(
    memory_manager: MemoryManager,
    memory_judge: MemoryJudge,
    user_id: int,
    user_message: str,
    rag_mode: bool = False,
) -> None:
    """
    Extract and store memories from user message using unified extraction + conflict detection.
    
    This reduces Ollama calls from 2-4+ to 1-2 per user message by:
    1. Fetching ALL existing memories upfront
    2. Passing them to extract_and_judge_memories() for conflict detection
    3. Using returned conflict info directly instead of calling evaluate_storage() per memory

    Args:
        memory_manager: Memory manager instance
        memory_judge: Memory judge instance
        user_id: User ID
        user_message: The user's message
    """
    try:
        # Fetch ALL existing memories for conflict detection
        existing_memories = _get_all_existing_memories(memory_manager, user_id)
        
        user_context = {"user_id": user_id} if existing_memories else None

        # Determine user language from stored preference (fallback to English)
        user_lang = get_user_language(memory_manager, user_id)

        # Use MemoryJudge to extract memories with conflict detection
        # This is the unified call that does extraction + conflict detection in one Ollama call
        extracted_memories = await memory_judge.extract_and_judge_memories(
            user_message=user_message,
            user_context=user_context,
            language=user_lang,
            existing_memories=existing_memories
        )

        logger.debug(f"user_id={user_id} user_message={user_message!r} extracted={extracted_memories}")

        for memory in extracted_memories:
            try:
                key = memory.get("key")
                val = memory.get("value")
                conflicts = memory.get("conflicts", [])  # Get conflicts from extraction
                memory_id = None  # Default to None
                
                # Route lesson state writes through the centralized helper
                if key == MemoryKey.LESSON_CURRENT:
                    # Normalize numeric lesson values to int, keep strings like 'continuing'
                    parsed = None
                    try:
                        parsed = int(val)
                    except Exception:
                        parsed = val
                    set_current_lesson(memory_manager, user_id, parsed)
                    memory_id = -1  # Lesson state handled differently
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
                    memory_id = -1  # Lesson state handled differently
                else:
                    # Handle conflicts from unified extraction directly
                    # No need to call evaluate_storage() separately - conflicts detected in extraction
                    for conflict in conflicts:
                        action = conflict.get("action", "FLAG")
                        existing_memory_id = conflict.get("existing_memory_id")
                        
                        if action == "REPLACE" and existing_memory_id:
                            logger.info(f"Unified extraction: Archiving memory {existing_memory_id} (replaced by new {key})")
                            memory_manager.archive_memories(user_id, [existing_memory_id])
                        elif action == "MERGE" and existing_memory_id:
                            logger.info(f"Unified extraction: Merging with memory {existing_memory_id}")
                        elif action == "FLAG" and existing_memory_id:
                            logger.warning(f"Unified extraction flagged {key}: {conflict.get('reason')}")
                    
                    # Store the memory directly (conflicts already handled)
                    memory_id = memory_manager.store_memory(
                        user_id=user_id,
                        key=key,
                        value=val,
                        confidence=memory.get("confidence", 1.0),
                        ttl_hours=memory.get("ttl_hours"),
                        source="dialogue_engine_extractor",
                    )
                
                sval = str(val) if val is not None else ''
                if memory_id is not None and memory_id != -1:
                    logger.debug(f"Memory saved: user={user_id} key={memory.get('key')} value={sval[:50]}")
                elif memory_id == -1:
                    logger.debug(f"Lesson state updated: user={user_id} key={memory.get('key')}")
                else:
                    logger.debug(f"Memory rejected by AI judge: user={user_id} key={memory.get('key')}")
            except Exception as e:
                logger.error(f"Error storing memory: {e}")

    except Exception as e:
        logger.error(f"Error in memory extraction: {e}")

