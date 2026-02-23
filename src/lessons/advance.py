from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm import Session

from src.models.database import Lesson

from .handler import format_lesson_message, translate_text
from src.memories.dialogue_helpers import get_user_language
from src.onboarding.prompts import get_lesson_confirmation_prompt
from src.lessons.state import set_last_sent_lesson_id
from src.memories.scheduler_helpers import set_pending_confirmation


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
    """Possibly return today's lesson message when user sends a simple greeting.

    Behavior:
    - If the computed state signals `need_confirmation`, return the
      localized confirmation prompt and do not send the lesson.
    - Only load and format the lesson when we're going to deliver it.
    - Persist `last_sent_lesson_id` after preparing the message.
    """
    context = prompt_builder.get_today_lesson_context(user_id)
    state = context.get("state", {})
    language = get_user_language(memory_manager, user_id)

    # Read lesson identifiers early so confirmation logic can reference them
    lesson_id = state.get("lesson_id")
    previous_lesson_id = state.get("previous_lesson_id")

    # If the computed state signals we need confirmation (user reported a
    # current lesson but we have no last_sent record), ask for confirmation
    # regardless of `advanced_by_day` so onboarding 'continuing' users are
    # prompted on first contact.  However we don't want to repeat the same
    # prompt multiple times in a single day/session; once a pending
    # confirmation exists we simply return None until it's resolved.
    if state.get("need_confirmation") and lesson_id and is_simple_greeting(text):
        # avoid re-sending the question if already pending
        from src.memories.scheduler_helpers import get_pending_confirmation

        if get_pending_confirmation(memory_manager, user_id):
            return None

        # Persist a pending confirmation so dialogue handlers can resolve it
        next_id = (int(lesson_id) % 365) + 1
        set_pending_confirmation(memory_manager, user_id, int(lesson_id), next_id)
        return get_lesson_confirmation_prompt(language, lesson_id)

    # Only proceed to auto-send when today's lesson was advanced by the
    # scheduler and the assistant was greeted with a short/simple greeting.
    if not state.get("advanced_by_day") or not is_simple_greeting(text):
        return None

    if not lesson_id:
        return None

    # Load the lesson and format the message for the user's language.
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
    if (language or "").lower() not in ["en"]:
        message = await translate_text(message, language, call_ollama)

    # Persist via consolidated lesson_state helper
    set_last_sent_lesson_id(memory_manager, user_id, lesson.lesson_id)

    return message
