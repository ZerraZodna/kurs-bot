from __future__ import annotations

import re
from typing import Callable

from sqlalchemy.orm import Session
from src.memories.constants import MemoryCategory, MemoryKey
from src.memories.dialogue_helpers import get_user_language
from src.scheduler import api as scheduler_api
from src.scheduler.domain import is_daily_schedule_family

# One-time reminder keyword parsing removed — handled by assistant + triggers
from src.services.dialogue.pause_handler import detect_pause_request


async def handle_schedule_messages(
    *,
    user_id: int,
    text: str,
    session: Session,
    memory_manager,
    onboarding_service,
    schedule_request_handler: Callable[[int, str, Session], str | None],
    call_ollama,
) -> str | None:
    # NOTE: We no longer pre-process schedule queries or one-time reminder keywords here.
    # Schedule queries, one-time reminders, and schedule changes should be handled by the
    # assistant (LLM) first and then dispatched via the trigger system.
    # This avoids premature/incorrect handling of user phrases like
    # "Add another reminder: Tell me 'I am loved!' in 5 minutes." or
    # "remind me next two hours to read the daily lesson" being treated as status queries.

    # Note: don't short-circuit schedule handling for RAG messages here.
    # RAG-specific behavior is handled later by the caller and prompt builder.
    if detect_pause_request(text):
        deactivated = scheduler_api.deactivate_user_schedules(user_id, session=session)
        if memory_manager:
            memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.SCHEDULE_REQUEST_PENDING,
                value="false",
                source="dialogue_engine",
                ttl_hours=1,
                category=MemoryCategory.CONVERSATION.value,
            )
        if deactivated > 0:
            response = "Okay — I paused your daily lessons. Tell me when you want to resume."
        else:
            response = "You don’t have any active lesson schedules to pause."
        language = get_user_language(memory_manager, user_id)
        from src.language import translate_text

        if language.lower() not in ["en"]:
            response = await translate_text(response, language, call_ollama)
        return response

    # Early explicit daily-set detection: handle explicit "daily" + time
    # instructions immediately, even if a `schedule_request_pending` flag
    # exists. This ensures user commands like "Set my daily reminder for
    # lessons to 09:00" take effect deterministically.
    lower = (text or "").lower()
    daily_indicators = ["daily", "every day", "each day", "every morning", "every evening", "hver dag", "daglig"]

    time_patterns = [
        r"(\d{1,2}:\d{2})",
        r"(\d{1,2}\s?(?:am|pm))",
        r"kl\s*(\d{1,2}(?::\d{2})?)",
        r"(\d{1,2})[.:](\d{2})",
    ]
    found_time = None
    for pat in time_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            found_time = m.group(0)
            break

    verb_indicators = ["set", "change", "change my", "set my", "endre", "endre min", "sett"]

    if any(ind in lower for ind in daily_indicators) and found_time and any(v in lower for v in verb_indicators):
        try:
            h, m = scheduler_api.parse_time_string(found_time)
            normalized = f"{h:02d}:{m:02d}"
        except Exception:
            normalized = found_time

        # Persist preferred time if memory manager available
        try:
            if memory_manager:
                memory_manager.store_memory(
                    user_id,
                    MemoryKey.PREFERRED_LESSON_TIME,
                    normalized,
                    category=MemoryCategory.PROFILE.value,
                    source="schedule_handlers",
                )
        except Exception:
            pass

        existing = scheduler_api.get_user_schedules(user_id, session=session)
        daily_existing = next((s for s in existing if is_daily_schedule_family(s.schedule_type)), None)
        if daily_existing:
            scheduler_api.update_daily_schedule(daily_existing.schedule_id, normalized, session=session)
            resp = f"Okay — I updated your daily reminder to {normalized}."
        else:
            scheduler_api.create_daily_schedule(user_id=user_id, lesson_id=None, time_str=normalized, session=session)
            resp = f"Perfect — I've scheduled your daily lessons for {normalized}."

        lang = None
        try:
            if memory_manager:
                lang = get_user_language(memory_manager, user_id)
        except Exception:
            lang = None
        from src.language import translate_text

        if lang and lang.lower() not in ("en",):
            resp = await translate_text(resp, lang, call_ollama)
        return resp

    if memory_manager:
        pending = memory_manager.get_memory(user_id, MemoryKey.SCHEDULE_REQUEST_PENDING)
        if pending and pending[0].get("value") == "true":
            schedule_response = await schedule_request_handler(user_id, text, session)
            if schedule_response:
                return schedule_response

    return None
