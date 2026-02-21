from __future__ import annotations

from typing import Optional
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from src.models.database import Lesson

from .lesson_handler import format_lesson_message, translate_text
from .memory_helpers import get_user_language
from src.onboarding.language.prompts import get_lesson_confirmation_prompt
from src.scheduler.lesson_state import set_last_sent_lesson_id
from src.scheduler.memory_utils import set_pending_confirmation
from src.scheduler.lesson_state_flow import determine_lesson_action
from src.triggers.trigger_matcher import get_trigger_matcher


async def is_trigger_greeting(text: str) -> bool:
    """Use trigger matcher embeddings to detect greetings."""
    if not text or not text.strip():
        return True
    matcher = get_trigger_matcher()
    matches = await matcher.match_triggers(text, top_k=3)
    for m in matches:
        if m.get("action_type") == "greeting" and m.get("score", 0) >= m.get("threshold", 0.55):
            return True
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
    # Derive 'today' with any debug day offset used in tests/debug flows
    try:
        day_offset = prompt_builder._get_debug_day_offset(user_id)
    except Exception:
        day_offset = 0
    today = (datetime.now(timezone.utc) + timedelta(days=day_offset)).date()

    decision = determine_lesson_action(memory_manager, user_id, today=today)
    language = get_user_language(memory_manager, user_id)

    # Confirmation path
    if decision.get("action") == "confirm" and await is_trigger_greeting(text):
        confirm_id = decision.get("confirmation_lesson_id") or decision.get("lesson_id")
        next_id = decision.get("next_lesson_id") or ((int(confirm_id) % 365) + 1 if confirm_id else None)
        if confirm_id and next_id:
            set_pending_confirmation(memory_manager, user_id, int(confirm_id), int(next_id))
            return get_lesson_confirmation_prompt(language, int(confirm_id))
        return None

    # Auto-send path only on simple greetings and when decision says send
    if decision.get("action") != "send" or not await is_trigger_greeting(text):
        return None

    lesson_id = decision.get("lesson_id")
    previous_lesson_id = decision.get("previous_lesson_id")

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
