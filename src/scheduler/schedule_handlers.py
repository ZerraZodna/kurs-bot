from __future__ import annotations

from typing import Optional, Callable

from sqlalchemy.orm import Session

from src.scheduler import SchedulerService
from src.scheduler.domain import is_daily_schedule_family
from src.services.timezone_utils import ensure_user_timezone
import re

# One-time reminder keyword parsing removed — handled by assistant + triggers
from src.services.dialogue.pause_handler import detect_pause_request
from src.scheduler.schedule_query_handler import detect_schedule_status_request, build_schedule_status_response
from src.memories.dialogue_helpers import get_user_language
from src.memories.constants import MemoryCategory, MemoryKey
from src.lessons.handler import translate_text


async def handle_schedule_messages(
    *,
    user_id: int,
    text: str,
    session: Session,
    memory_manager,
    onboarding_service,
    schedule_request_handler: Callable[[int, str, Session], Optional[str]],
    call_ollama,
    use_rag_for_this_message: bool = False,
) -> Optional[str]:
    # NOTE: We no longer pre-process one-time reminder keywords here.
    # One-time reminders and schedule changes should be handled by the
    # assistant (LLM) first and then dispatched via the trigger system.
    # This avoids premature/incorrect handling of user phrases like
    # "Add another reminder: Tell me 'I am loved!' in 5 minutes."

    if await detect_schedule_status_request(text):
        schedules = SchedulerService.get_user_schedules(user_id)
        tz_name = ensure_user_timezone(
            memory_manager,
            user_id,
            get_user_language(memory_manager, user_id),
            source="dialogue_engine_schedule_status",
        )
        response = build_schedule_status_response(schedules, tz_name)
        language = get_user_language(memory_manager, user_id)
        if language.lower() not in ["en"]:
            response = await translate_text(response, language, call_ollama)
        return response

    # Note: don't short-circuit schedule handling for RAG messages here.
    # RAG-specific behavior is handled later by the caller and prompt builder.
    if detect_pause_request(text):
        deactivated = SchedulerService.deactivate_user_schedules(user_id, session=session)
        if memory_manager:
            memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.SCHEDULE_REQUEST_PENDING,
                value="false",
                confidence=1.0,
                source="dialogue_engine",
                ttl_hours=1,
                category=MemoryCategory.CONVERSATION.value,
            )
        if deactivated > 0:
            response = "Okay — I paused your daily lessons. Tell me when you want to resume."
        else:
            response = "You don’t have any active lesson schedules to pause."
        language = get_user_language(memory_manager, user_id)
        if language.lower() not in ["en"]:
            response = await translate_text(response, language, call_ollama)
        return response

    # Early explicit daily-set detection: handle explicit "daily" + time
    # instructions immediately, even if a `schedule_request_pending` flag
    # exists. This ensures user commands like "Set my daily reminder for
    # lessons to 09:00" take effect deterministically.
    lower = (text or "").lower()
    daily_indicators = ["daily", "every day", "each day", "every morning", "every evening", "hver dag", "daglig"]

    time_patterns = [r"(\d{1,2}:\d{2})", r"(\d{1,2}\s?(?:am|pm))", r"kl\s*(\d{1,2}(?::\d{2})?)", r"(\d{1,2})[.:](\d{2})"]
    found_time = None
    for pat in time_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            found_time = m.group(0)
            break

    verb_indicators = ["set", "change", "change my", "set my", "endre", "endre min", "sett"]

    if any(ind in lower for ind in daily_indicators) and found_time and any(v in lower for v in verb_indicators):
        try:
            h, m = SchedulerService.parse_time_string(found_time)
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

        existing = SchedulerService.get_user_schedules(user_id)
        daily_existing = next((s for s in existing if is_daily_schedule_family(s.schedule_type)), None)
        if daily_existing:
            SchedulerService.update_daily_schedule(daily_existing.schedule_id, normalized, session=session)
            resp = f"Okay — I updated your daily reminder to {normalized}."
        else:
            SchedulerService.create_daily_schedule(user_id=user_id, lesson_id=None, time_str=normalized, session=session)
            resp = f"Perfect — I've scheduled your daily lessons for {normalized}."

        lang = None
        try:
            if memory_manager:
                lang = get_user_language(memory_manager, user_id)
        except Exception:
            lang = None
        if lang and lang.lower() not in ("en",):
            resp = await translate_text(resp, lang, call_ollama)
        return resp

    if memory_manager:
        pending = memory_manager.get_memory(user_id, MemoryKey.SCHEDULE_REQUEST_PENDING)
        if pending and pending[0].get("value") == "true":
            schedule_response = await schedule_request_handler(user_id, text, session)
            if schedule_response:
                return schedule_response

    if onboarding_service and onboarding_service.detect_schedule_request(text):
        # Only treat explicit "daily" style requests as pre-LLM daily schedule flows.
        # One-time reminders (e.g., "Remind me tomorrow at 12:00") should be handled
        # by the assistant and dispatched via triggers, not blocked by an existing
        # daily schedule. We therefore require a clear daily indicator before
        # invoking the schedule_request_handler here.
        lower = (text or "").lower()
        daily_indicators = ["daily", "every day", "each day", "every morning", "every evening", "hver dag", "daglig"]

        # Fallback: when daily indicator is present but not deterministic, fall back to the prior behavior
        if any(ind in lower for ind in daily_indicators):
            if memory_manager:
                memory_manager.store_memory(
                    user_id=user_id,
                    key=MemoryKey.SCHEDULE_REQUEST_PENDING,
                    value="true",
                    confidence=1.0,
                    source="dialogue_engine",
                    ttl_hours=1,
                    category=MemoryCategory.CONVERSATION.value,
                )
            schedule_response = await schedule_request_handler(user_id, text, session)
            if schedule_response:
                return schedule_response

    return None
