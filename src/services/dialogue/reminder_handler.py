"""Reminder and confirmation handling logic."""

from __future__ import annotations

import json
import logging
import re
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from src.services.timezone_utils import to_utc
from sqlalchemy.orm import Session
from src.models.database import Lesson
from src.memories import MemoryManager
from src.memories.constants import MemoryCategory, MemoryKey
from src.lessons.state import (
    get_last_sent_lesson_id,
    set_current_lesson,
    set_last_sent_lesson_id,
)
from src.lessons.state_flow import apply_reported_progress
from src.scheduler.memory_helpers import (
    is_auto_advance_lessons_enabled,
    set_auto_advance_lessons_preference,
)
logger = logging.getLogger(__name__)


def _detect_auto_advance_preference_intent(text: str) -> Optional[bool]:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    if not normalized:
        return None

    if re.search(
        r"\b(?:don't|dont|do not|stop)\s+(?:auto[-\s]*)?assume\b",
        normalized,
    ):
        return False
    if re.search(r"\bask me before\b.*\b(?:next lesson|advance)\b", normalized):
        return False

    has_assume = "assume" in normalized
    has_lesson = "lesson" in normalized
    has_day = (
        "each day" in normalized
        or "every day" in normalized
        or "daily" in normalized
        or "a day" in normalized
    )
    if has_assume and has_lesson and has_day:
        return True

    if re.search(r"\bskip\b.*\b(?:daily )?lesson confirmation\b", normalized):
        return True
    if re.search(
        r"\bno need\b.*\b(?:ask|confirmation)\b.*\b(?:lesson|daily)\b",
        normalized,
    ):
        return True

    return None


def _is_progress_override_negative(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    if not normalized:
        return False
    patterns = [
        r"\bi (?:did not|didn't|didnt) (?:do|finish|complete) (?:it|that|the lesson)\b",
        r"\bi (?:have not|haven't|havent) (?:done|finished|completed) (?:it|the lesson)\b",
        r"\bi was not able to (?:do|finish|complete) (?:it|the lesson)\b",
    ]
    return any(re.search(pattern, normalized) for pattern in patterns)


async def _semantic_yes_no(text: str, onboarding_service) -> (bool, bool):
    """Classify yes/no using simple keyword matching."""
    import re
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    
    # Simple keyword-based classification
    yes_patterns = [
        r"\byes\b", r"\byeah\b", r"\byep\b", r"\bsure\b", r"\bok\b", r"\bokay\b",
        r"\bdone\b", r"\bcompleted\b", r"\bfinished\b", r"\bdid it\b"
    ]
    no_patterns = [
        r"\bno\b", r"\bnope\b", r"\bnot yet\b", r"\bdidn't\b", r"\bdid not\b",
        r"\bnot done\b", r"\bnot finished\b", r"\bnot completed\b"
    ]
    
    is_yes = any(re.search(p, normalized) for p in yes_patterns)
    is_no = any(re.search(p, normalized) for p in no_patterns)
    
    return is_yes, is_no


def get_pending_confirmation(
    memory_manager: MemoryManager, user_id: int
) -> Optional[dict]:
    """
    Get pending lesson confirmation state.

    Returns:
        Dict with lesson_id and next_lesson_id if pending, None otherwise
    """
    memories = memory_manager.get_memory(user_id, MemoryKey.LESSON_CONFIRMATION_PENDING)
    if not memories:
        return None

    def _normalize_dt(value: Optional[datetime]) -> datetime:
        if isinstance(value, datetime):
            return to_utc(value)
        return datetime.min.replace(tzinfo=timezone.utc)

    latest = max(memories, key=lambda m: _normalize_dt(m.get("created_at")))
    raw = latest.get("value", "")
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("lesson_id"):
            return data
    except Exception:
        return None
    return None


def resolve_pending_confirmation(memory_manager: MemoryManager, user_id: int) -> None:
    """Mark lesson confirmation as resolved."""
    memory_manager.store_memory(
        user_id=user_id,
        key=MemoryKey.LESSON_CONFIRMATION_PENDING,
        value=json.dumps(
            {"resolved": True, "timestamp": datetime.now(timezone.utc).isoformat()}
        ),
        category=MemoryCategory.CONVERSATION.value,
        ttl_hours=12,
        source="dialogue_engine",
    )


async def handle_lesson_confirmation(
    user_id: int,
    text: str,
    session: Session,
    memory_manager: MemoryManager,
    onboarding_service,
    translate_fn,
    get_language_fn,
    format_lesson_fn,
) -> Optional[str]:
    """
    Handle user's response to lesson completion confirmation.

    Args:
        user_id: User ID
        text: User's response
        session: Database session
        memory_manager: Memory manager instance
        onboarding_service: Onboarding service
        translate_fn: Function to translate text
        get_language_fn: Function to get user's language
        format_lesson_fn: Function to format lesson message

    Returns:
        Response message or None if not a confirmation response
    """
    message_lower = text.lower().strip()
    pref_update = _detect_auto_advance_preference_intent(message_lower)
    if pref_update is not None:
        set_auto_advance_lessons_preference(
            memory_manager,
            user_id,
            pref_update,
            source="dialogue_auto_advance_preference",
        )

    pending = get_pending_confirmation(memory_manager, user_id)
    auto_advance_enabled = is_auto_advance_lessons_enabled(memory_manager, user_id)
    if not pending:
        if pref_update is True:
            return (
                "Understood. I'll auto-advance one lesson per day and skip the daily confirmation prompt. "
                "If you didn't do a lesson, just tell me."
            )
        if pref_update is False:
            return "Okay, I will ask for confirmation before moving to the next lesson."

        if auto_advance_enabled and _is_progress_override_negative(message_lower):
            last_sent = get_last_sent_lesson_id(memory_manager, user_id)
            if last_sent is None:
                return "No problem. I can pause progression whenever you tell me."

            repeat_lesson = max(int(last_sent) - 1, 1)
            set_current_lesson(memory_manager, user_id, repeat_lesson)
            set_last_sent_lesson_id(memory_manager, user_id, repeat_lesson)
            return (
                f"No problem. I'll pause progression and keep you on Lesson {repeat_lesson}. "
                "Tell me when you're ready to continue."
            )

        return None

    # First, look for explicit lesson numbers in the reply (e.g., "on lesson 8").
    # When present we treat the highest lesson number as the user's current lesson
    # and infer the last completed lesson as `current - 1`. This lets us recover
    # after outages or gaps without relying solely on a yes/no response.
    lesson_numbers = [
        int(m)
        for m in re.findall(r"lesson\s*(\d{1,3})", message_lower)
        if 1 <= int(m) <= 365
    ]
    if pending and lesson_numbers:
        current_lesson = max(lesson_numbers)
        progress = apply_reported_progress(memory_manager, user_id, current_lesson)

        lesson = (
            session.query(Lesson).filter(Lesson.lesson_id == current_lesson).first()
            if current_lesson
            else None
        )

        resolve_pending_confirmation(memory_manager, user_id)

        if not lesson:
            return "Thanks for the update! I couldn't find that lesson right now."

        language = get_language_fn(user_id)
        message = await format_lesson_fn(lesson, language)

        # Track last delivered lesson for scheduling/advancement logic
        set_last_sent_lesson_id(memory_manager, user_id, lesson.lesson_id)

        return message

    if pref_update is True:
        is_yes, is_no = True, False
    else:
        is_yes, is_no = await _semantic_yes_no(message_lower, onboarding_service)

    if not is_yes and not is_no and _is_progress_override_negative(message_lower):
        is_no = True

    if not is_yes and not is_no:
        return None

    lesson_id = pending.get("lesson_id")
    next_id = pending.get("next_lesson_id")

    if is_no:
        resolve_pending_confirmation(memory_manager, user_id)
        message = "No problem. Take your time and reply 'yes' when you're ready to continue."
        language = get_language_fn(user_id)
        if language and isinstance(language, str) and language.lower() not in ["en"]:
            message = await translate_fn(message, language)
        return message

    # Yes: mark completed and send next lesson
    if lesson_id:
            memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.LESSON_COMPLETED,
                value=str(lesson_id),
                category=MemoryCategory.PROGRESS.value,
                confidence=1.0,
                source="dialogue_engine_lesson_confirmation",
            )

    # Update explicit current_lesson state to the next lesson (if known).
    if lesson_id:
        next_id = lesson_id + 1 if lesson_id < 365 else 365
        set_current_lesson(memory_manager, user_id, next_id)

    lesson = (
        session.query(Lesson).filter(Lesson.lesson_id == next_id).first()
        if next_id
        else None
    )
    if not lesson:
        # Try centralized helper to import bundled lessons if DB is empty
        try:
            from src.lessons.importer import ensure_lessons_available

            ok = ensure_lessons_available(session)
            if ok:
                lesson = session.query(Lesson).filter(Lesson.lesson_id == next_id).first()
        except Exception:
            lesson = None

    if not lesson:
        resolve_pending_confirmation(memory_manager, user_id)
        return "Thanks! I couldn't find the next lesson right now."

    language = get_language_fn(user_id)
    message = await format_lesson_fn(lesson, language)

    # Persist the last lesson we sent using consolidated lesson_state helper
    set_last_sent_lesson_id(memory_manager, user_id, lesson.lesson_id)

    resolve_pending_confirmation(memory_manager, user_id)
    return message
