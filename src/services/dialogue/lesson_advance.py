from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm import Session

from src.models.database import Lesson

from .lesson_handler import format_lesson_message, translate_text
from .memory_helpers import get_user_language


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
    context = prompt_builder.get_today_lesson_context(user_id)
    lesson_text = context.get("lesson_text", "")
    state = context.get("state", {})
    if not lesson_text or not state.get("advanced_by_day"):
        return None

    if not is_simple_greeting(text):
        return None

    lesson_id = state.get("lesson_id")
    previous_lesson_id = state.get("previous_lesson_id")
    if not lesson_id:
        return None

    lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
    if not lesson:
        return None

    language = get_user_language(memory_manager, user_id)
    message = await format_lesson_message(lesson, language, call_ollama)

    repeat_note = None
    if previous_lesson_id:
        repeat_note = f"If you'd like to repeat Lesson {previous_lesson_id} instead, just let me know."
        if language.lower() not in ["english", "en"]:
            repeat_note = await translate_text(repeat_note, language, call_ollama)

    if repeat_note:
        message = f"{message}\n\n{repeat_note}"

    memory_manager.store_memory(
        user_id=user_id,
        key="last_sent_lesson_id",
        value=str(lesson.lesson_id),
        category="progress",
        confidence=1.0,
        source="dialogue_engine_auto_lesson",
    )

    return message
