"""Memory extraction and user utilities."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from src.memories.manager import MemoryManager
from src.memories.memory_extractor import MemoryExtractor
from src.memories.constants import MemoryKey
from src.memories.user_data_service import delete_user_content_rows
from src.config import settings
from src.lessons.state import set_current_lesson

logger = logging.getLogger(__name__)

def get_user_language(memory_manager: MemoryManager, user_id: int) -> str:
    #"""Get user's preferred language."""
    memories = memory_manager.get_memory(user_id, MemoryKey.USER_LANGUAGE)
    ## Stored values are ISO codes (e.g., 'en', 'no'). Return stored value or 'en'.
    return memories[0].get("value", "en") if memories else "en"



async def extract_and_store_memories(
    memory_manager: MemoryManager,
    memory_extractor: MemoryExtractor,
    user_id: int,
    user_message: str,
    rag_mode: bool = False,
) -> None:
    """
    Extract and store memories from user message.

    Args:
        memory_manager: Memory manager instance
        memory_extractor: Memory extractor instance
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

        # Use the RAG chat model for memory extraction by default because it
        # produces more reliable classification for factual extractions
        model_override = settings.OLLAMA_CHAT_RAG_MODEL
        # Determine user language from stored preference (fallback to English)
        user_lang = get_user_language(memory_manager, user_id)

        extracted_memories = await memory_extractor.extract_memories(
            user_message, user_context, model_override=model_override, language=user_lang
        )

        print(f"[EXTRACT DEBUG] user_id={user_id} user_message={user_message!r} extracted={extracted_memories}")

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
                else:
                    memory_manager.store_memory(
                        user_id=user_id,
                        key=key,
                        value=val,
                        confidence=memory.get("confidence", 1.0),
                        ttl_hours=memory.get("ttl_hours"),
                        source="dialogue_engine_extractor",
                    )
                print(f"[EXTRACT DEBUG] stored memory for user {user_id}: {memory.get('key')}={memory.get('value')}")
                val = memory.get('value')
                sval = str(val) if val is not None else ''
                logger.info(f"Stored memory for user {user_id}: {memory.get('key')}={sval[:50]}")
            except Exception as e:
                logger.error(f"Error storing memory: {e}")

    except Exception as e:
        logger.error(f"Error in memory extraction: {e}")


def delete_user_and_data(db: Session, user_id: int) -> None:
    """
    Delete a user and all associated data.

    Called when user declines consent during onboarding.
    """
    try:
        from src.models.database import User

        delete_user_content_rows(db, user_id)
        db.query(User).filter_by(user_id=user_id).delete(synchronize_session=False)

        db.commit()
        logger.info(f"[User deleted] User {user_id} deleted due to declined consent")
    except Exception as e:
        logger.error(f"[User deletion error] Failed to delete user {user_id}: {e}")
        db.rollback()
