"""Reminder and confirmation handling logic."""

from __future__ import annotations

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from src.models.database import Lesson
from src.services.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


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
            return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
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

    is_yes = (
        onboarding_service.detect_commitment_keywords(message_lower)
        if onboarding_service
        else False
    )
    no_keywords = [
        "no",
        "not yet",
        "nope",
        "nei",
        "ikke ennå",
        "ikke enda",
        "ikke",
        "ikke ferdig",
        "senere",
    ]
    is_no = any(k in message_lower for k in no_keywords)

    if not is_yes and not is_no:
        return None

    lesson_id = pending.get("lesson_id")
    next_id = pending.get("next_lesson_id")

    if is_no:
        resolve_pending_confirmation(memory_manager, user_id)
        message = "No problem. Take your time and reply 'yes' when you're ready to continue."
        language = get_language_fn(user_id)
        if language.lower() not in ["english", "en"]:
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

    lesson = (
        session.query(Lesson).filter(Lesson.lesson_id == next_id).first()
        if next_id
        else None
    )
    if not lesson:
        resolve_pending_confirmation(memory_manager, user_id)
        return "Thanks! I couldn't find the next lesson right now."

    language = get_language_fn(user_id)
    message = await format_lesson_fn(lesson, language)

    memory_manager.store_memory(
        user_id=user_id,
        key="last_sent_lesson_id",
        value=str(lesson.lesson_id),
        category="progress",
        confidence=1.0,
        source="dialogue_engine_lesson_confirmation",
    )

    resolve_pending_confirmation(memory_manager, user_id)
    return message
