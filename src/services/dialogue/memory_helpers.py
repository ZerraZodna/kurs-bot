"""Memory extraction and user utilities."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional
from langdetect import detect, LangDetectException
from sqlalchemy.orm import Session
from src.services.memory_manager import MemoryManager
from src.services.memory_extractor import MemoryExtractor
from src.config import settings

logger = logging.getLogger(__name__)


def get_user_language(memory_manager: MemoryManager, user_id: int) -> str:
    """Get user's preferred language."""
    memories = memory_manager.get_memory(user_id, "user_language")
    return memories[0].get("value", "English") if memories else "English"


async def detect_and_store_language(
    memory_manager: MemoryManager, user_id: int, user_message: str
) -> None:
    """
    Detect user's language from message and store if confident.

    Handles multipart names, Norwegian keywords, etc.
    """
    try:
        existing_lang = memory_manager.get_memory(user_id, "user_language")
        existing_value = existing_lang[0].get("value") if existing_lang else None

        norwegian_keywords = [
            "jeg heter",
            "hvordan går",
            "vær så snill",
            "god morgen",
            "god kveld",
            "god ettermiddag",
        ]
        norwegian_single_words = {
            "hei",
            "jeg",
            "heter",
            "hvordan",
            "takk",
            "lyst",
            "ikke",
            "ja",
            "nei",
        }
        english_keywords = [
            "good morning",
            "good evening",
            "good afternoon",
            "how are",
            "what is",
        ]
        english_single_words = {
            "hello",
            "hi",
            "i",
            "you",
            "the",
            "and",
            "please",
            "thank",
        }

        msg_lower = user_message.lower()
        tokens = re.findall(r"[a-zA-Z]+", msg_lower)
        token_set = set(tokens)
        word_count = len(user_message.split())

        has_no_keywords = any(kw in msg_lower for kw in norwegian_keywords) or any(
            kw in token_set for kw in norwegian_single_words
        )
        has_en_keywords = any(kw in msg_lower for kw in english_keywords) or any(
            kw in token_set for kw in english_single_words
        )

        stripped_message = user_message.strip()
        is_probable_name = (
            word_count <= 2
            and stripped_message[:1].isupper()
            and stripped_message.replace(" ", "").isalpha()
            and not (has_no_keywords or has_en_keywords)
        )

        detected_lang = None
        if word_count <= 3 and has_no_keywords:
            detected_lang = "no"
        elif word_count <= 3 and has_en_keywords:
            detected_lang = "en"
        elif word_count < 4 and not (has_no_keywords or has_en_keywords):
            detected_lang = None
        else:
            try:
                detected_lang = detect(user_message)
            except LangDetectException:
                if has_no_keywords:
                    detected_lang = "no"
                elif has_en_keywords:
                    detected_lang = "en"

        # Guard against NL misclassification
        if detected_lang in ["nl", "de", "sv", "da", "sl"] and has_no_keywords:
            detected_lang = "no"

        lang_names = {
            "no": "Norwegian",
            "nb": "Norwegian",
            "nn": "Norwegian",
            "en": "English",
            "sv": "Swedish",
            "da": "Danish",
            "de": "German",
            "fr": "French",
            "es": "Spanish",
            "it": "Italian",
            "pt": "Portuguese",
            "ru": "Russian",
            "ja": "Japanese",
            "zh-cn": "Chinese",
        }

        lang_name = lang_names.get(detected_lang, detected_lang.upper()) if detected_lang else None

        # If we already have a stored language, avoid changing it based on
        # very short messages (<= 4 words). This prevents accidental
        # overrides from brief replies like "yes" or a short name.
        should_update = False
        if is_probable_name:
            should_update = False
        elif not existing_value and lang_name:
            should_update = True
        elif lang_name and lang_name != existing_value:
            # Do not overwrite an existing detected language for short messages
            if existing_value and word_count <= 4:
                should_update = False
            else:
                if word_count >= 4 and (has_no_keywords or has_en_keywords):
                    should_update = True
                elif has_no_keywords and lang_name == "Norwegian":
                    should_update = True
                elif has_en_keywords and lang_name == "English":
                    should_update = True

        if should_update:
            memory_manager.store_memory(
                user_id=user_id,
                key="user_language",
                value=lang_name,
                confidence=0.9,
                source="dialogue_engine_language_detection",
                category="preference",
            )
            logger.info(f"Detected language for user {user_id}: {lang_name}")

    except LangDetectException as e:
        logger.warning(f"Could not detect language: {e}")


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
        for key in ["first_name", "acim_commitment", "learning_goal"]:
            memories = memory_manager.get_memory(user_id, key)
            if memories:
                existing_memories[key] = memories[0].get("value")

        user_context = (
            {"user_id": user_id, "existing_memories": existing_memories}
            if existing_memories
            else None
        )

        model_override = settings.MEMORY_EXTRACTOR_RAG_MODEL if rag_mode else None
        extracted_memories = await memory_extractor.extract_memories(
            user_message, user_context, model_override=model_override
        )

        for memory in extracted_memories:
            try:
                memory_manager.store_memory(
                    user_id=user_id,
                    key=memory.get("key"),
                    value=memory.get("value"),
                    confidence=memory.get("confidence", 1.0),
                    ttl_hours=memory.get("ttl_hours"),
                    source="dialogue_engine_extractor",
                    generate_embedding=False,  # Disable embedding to avoid lock contention
                )
                logger.info(
                    f"Stored memory for user {user_id}: {memory.get('key')}="
                    f"{memory.get('value')[:50]}"
                )
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
        from src.models.database import Memory, Schedule, MessageLog, User

        db.query(Memory).filter_by(user_id=user_id).delete(synchronize_session=False)
        db.query(Schedule).filter_by(user_id=user_id).delete(
            synchronize_session=False
        )
        db.query(MessageLog).filter_by(user_id=user_id).delete(
            synchronize_session=False
        )
        db.query(User).filter_by(user_id=user_id).delete(synchronize_session=False)

        db.commit()
        logger.info(f"[User deleted] User {user_id} deleted due to declined consent")
    except Exception as e:
        logger.error(f"[User deletion error] Failed to delete user {user_id}: {e}")
        db.rollback()
