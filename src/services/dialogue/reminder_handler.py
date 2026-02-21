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
from src.scheduler.lesson_state import set_last_sent_lesson_id
from src.scheduler.lesson_state_flow import apply_reported_progress
from src.triggers.trigger_matcher import get_trigger_matcher

logger = logging.getLogger(__name__)

async def _semantic_yes_no(text: str, onboarding_service) -> (bool, bool):
    """Classify yes/no using trigger embeddings; no keyword fallback."""
    matcher = get_trigger_matcher()
    matches = await matcher.match_triggers(text, top_k=3)
    yes_score = max(
        (m.get("score", 0) for m in matches if m.get("action_type") == "confirm_yes"),
        default=0.0,
    )
    yes_thresh = max(
        (m.get("threshold", 0.55) for m in matches if m.get("action_type") == "confirm_yes"),
        default=0.55,
    )
    no_score = max(
        (m.get("score", 0) for m in matches if m.get("action_type") == "confirm_no"),
        default=0.0,
    )
    no_thresh = max(
        (m.get("threshold", 0.55) for m in matches if m.get("action_type") == "confirm_no"),
        default=0.55,
    )
    is_yes = yes_score >= yes_thresh and yes_score > no_score
    is_no = no_score >= no_thresh and no_score > yes_score
    return is_yes, is_no


def get_pending_confirmation(
    memory_manager: MemoryManager, user_id: int
) -> Optional[dict]:
    """
    Get pending lesson confirmation state.

    Returns:
        Dict with lesson_id and next_lesson_id if pending, None otherwise
    """
    memories = memory_manager.get_memory(user_id, "lesson_confirmation_pending")
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
        key="lesson_confirmation_pending",
        value=json.dumps(
            {"resolved": True, "timestamp": datetime.now(timezone.utc).isoformat()}
        ),
        category="conversation",
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
    pending = get_pending_confirmation(memory_manager, user_id)
    if not pending:
        return None

    message_lower = text.lower().strip()

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

    is_yes, is_no = await _semantic_yes_no(message_lower, onboarding_service)

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
            key="lesson_completed",
            value=str(lesson_id),
            category="progress",
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
            from src.services.lesson_importer import ensure_lessons_available

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
