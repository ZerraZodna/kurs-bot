from __future__ import annotations

from typing import Optional, Callable

from sqlalchemy.orm import Session

from src.services.scheduler import SchedulerService
from src.services.timezone_utils import ensure_user_timezone
import re

from .reminder_handler import detect_one_time_reminder
from .pause_handler import detect_pause_request
from .schedule_query_handler import detect_schedule_status_request, build_schedule_status_response
from .memory_helpers import get_user_language
from .lesson_handler import translate_text


async def handle_schedule_messages(
    *,
    user_id: int,
    text: str,
    session: Session,
    memory_manager,
    onboarding_service,
    schedule_request_handler: Callable[[int, str, Session], Optional[str]],
    call_ollama,
) -> Optional[str]:
    reminder = detect_one_time_reminder(text)
    if reminder:
        SchedulerService.create_one_time_schedule(
            user_id=user_id,
            run_at=reminder["run_at"],
            message=reminder["message"],
            session=session,
        )
        confirmation = reminder["confirmation"]
        language = get_user_language(memory_manager, user_id)
        if language.lower() not in ["english", "en"]:
            confirmation = await translate_text(confirmation, language, call_ollama)
        return confirmation

    if detect_schedule_status_request(text):
        schedules = SchedulerService.get_user_schedules(user_id)
        tz_name = ensure_user_timezone(
            memory_manager,
            user_id,
            get_user_language(memory_manager, user_id),
            source="dialogue_engine_schedule_status",
        )
        response = build_schedule_status_response(schedules, tz_name)
        language = get_user_language(memory_manager, user_id)
        if language.lower() not in ["english", "en"]:
            response = await translate_text(response, language, call_ollama)
        return response

    if detect_pause_request(text):
        deactivated = SchedulerService.deactivate_user_schedules(user_id, session=session)
        if memory_manager:
            memory_manager.store_memory(
                user_id=user_id,
                key="schedule_request_pending",
                value="false",
                confidence=1.0,
                source="dialogue_engine",
                ttl_hours=1,
                category="conversation",
            )
        if deactivated > 0:
            response = "Okay — I paused your daily lessons. Tell me when you want to resume."
        else:
            response = "You don’t have any active lesson schedules to pause."
        language = get_user_language(memory_manager, user_id)
        if language.lower() not in ["english", "en"]:
            response = await translate_text(response, language, call_ollama)
        return response

    if memory_manager:
        pending = memory_manager.get_memory(user_id, "schedule_request_pending")
        if pending and pending[0].get("value") == "true":
            schedule_response = await schedule_request_handler(user_id, text, session)
            if schedule_response:
                return schedule_response

    if onboarding_service and onboarding_service.detect_schedule_request(text):
        if memory_manager:
            memory_manager.store_memory(
                user_id=user_id,
                key="schedule_request_pending",
                value="true",
                confidence=1.0,
                source="dialogue_engine",
                ttl_hours=1,
                category="conversation",
            )
        schedule_response = await schedule_request_handler(user_id, text, session)
        if schedule_response:
            return schedule_response

    return None
