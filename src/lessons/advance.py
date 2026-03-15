from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm import Session
from datetime import datetime, timezone

from src.memories.constants import MemoryCategory, MemoryKey
from src.models.database import Lesson
from src.models.user import User
from src.lessons.state import compute_current_lesson_state

from .handler import format_lesson_message, translate_text
from src.memories.dialogue_helpers import get_user_language


def is_simple_greeting(text: str) -> bool:
    cleaned = re.sub(r"[^a-zA-Z\s]", "", text or "").strip().lower()
    if not cleaned:
        return True
    if len(cleaned.split()) <= 3:
        greetings = {
            "hi",
            "hello",
            "hey",
            "good morning",
            "good evening",
            "good afternoon",
            "morning",
            "evening",
            "afternoon",
            "hei",
            "hallo",
            "god morgen",
            "god kveld",
            "god ettermiddag",
        }
        return cleaned in greetings
    return False


async def maybe_send_next_lesson(
    *,
    user_id: int,
    text: str,
    session: Session,
    prompt_builder,
    memory_manager,
    call_ollama,
) -> Optional[str]:
    """Possibly return today's lesson message when user sends a simple greeting on new day.

    Sends lesson if new day (advanced_by_day) + greeting.
    Updates last_active_at and lesson state consistently.
    """
    state = compute_current_lesson_state(memory_manager, user_id)
    language = get_user_language(memory_manager, user_id)

    if not state.get("advanced_by_day"):
        return None

    # TODO: Removed greeting trigger per user request - let "Hi" reach LLM chat
    # Original: or not is_simple_greeting(text)
    return None

    lesson_id = state["lesson_id"]
    if not lesson_id:
        return None

    lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
    if not lesson:
        return None

    # Get  lesson in English, translate only once
    message = await format_lesson_message(lesson, "en", call_ollama)

    # Optionally offer to repeat the previous lesson.
    previous_lesson_id = state.get("previous_lesson_id")
    if previous_lesson_id:
        repeat_note = f"If you'd like to repeat Lesson {previous_lesson_id} instead, just let me know."
        message = f"{message}\n\n{repeat_note}"
        
        # Store what lesson was offered for repeat so we can handle "Yes, repeat" later
        memory_manager.store_memory(
            user_id=user_id,
            key=MemoryKey.LESSON_REPEAT_OFFERED,
            value=str(previous_lesson_id),
            category=MemoryCategory.PROGRESS.value,
            source="advance.py",
        )
    
    if (language or "").lower() not in ["en"]:
        message = await translate_text(message, language, call_ollama)

    # Persist advance: update date and lesson state
    user = session.query(User).filter(User.user_id == user_id).first()
    user.last_active_at = datetime.now(timezone.utc)
    session.commit()

    return message

