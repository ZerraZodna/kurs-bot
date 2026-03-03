"""Public API facade for lesson operations.

This module provides a unified public API for all lesson-related operations.
Other modules should import from here rather than directly from internal
lesson modules.
"""

import logging
from typing import Optional, Dict, Any
from datetime import date

from sqlalchemy.orm import Session

from src.models.database import Lesson
from src.memories.manager import MemoryManager

# Import from internal modules
from src.lessons.state import (
    get_lesson_state as _get_lesson_state,
    set_lesson_state as _set_lesson_state,
    get_current_lesson as _get_current_lesson,
    set_current_lesson as _set_current_lesson,
    get_last_sent_lesson_id as _get_last_sent_lesson_id,
    set_last_sent_lesson_id as _set_last_sent_lesson_id,
    has_lesson_status as _has_lesson_status,
    compute_current_lesson_state as _compute_current_lesson_state,
)
from src.lessons.handler import (
    detect_lesson_request as _detect_lesson_request,
    format_lesson_message as _format_lesson_message,
    _find_lesson_by_id as _find_lesson,
    handle_lesson_request as _handle_lesson_request,
    process_lesson_query as _process_lesson_query,
)
from src.lessons.advance import maybe_send_next_lesson as _maybe_send_next_lesson
from src.lessons.state_flow import apply_reported_progress as _apply_reported_progress

logger = logging.getLogger(__name__)


def get_lesson(lesson_id: int, session: Session) -> Optional[Lesson]:
    """Retrieve a lesson by ID.
    
    Args:
        lesson_id: The lesson number (1-365)
        session: Database session
        
    Returns:
        Lesson object or None if not found
    """
    return _find_lesson(session, lesson_id)


def format_lesson_message(lesson: Lesson, language: Optional[str] = None) -> str:
    """Format a lesson for display.
    
    Args:
        lesson: Lesson object from database
        language: Target language for translation (None for no translation)
        
    Returns:
        Formatted lesson text
    """
    # Note: This is async in handler.py, but we provide a sync wrapper
    # For async usage, use the handler directly
    import asyncio
    try:
        return asyncio.run(_format_lesson_message(lesson, language))
    except Exception as e:
        logger.warning(f"Failed to format lesson message: {e}")
        # Fallback to basic formatting
        return f"Lesson {lesson.lesson_id}: {lesson.title}\n\n{lesson.content}"


async def deliver_lesson(
    user_id: int,
    lesson_id: int,
    session: Session,
    language: Optional[str] = None,
    call_ollama_fn: Optional[Any] = None,
) -> str:
    """Deliver a lesson to a user.
    
    This retrieves the lesson, formats it, and returns the formatted message.
    Note: This does not send the lesson, just prepares the content.
    
    Args:
        user_id: User ID
        lesson_id: Lesson ID to deliver
        session: Database session
        language: Target language
        call_ollama_fn: Optional function for translation
        
    Returns:
        Formatted lesson message ready to send
    """
    lesson = get_lesson(lesson_id, session)
    if not lesson:
        return f"I couldn't find lesson {lesson_id} in my database. ACIM has 365 lessons - please ask for a lesson between 1 and 365."
    
    return await _format_lesson_message(lesson, language, call_ollama_fn)


def detect_lesson_request(text: str) -> Optional[Dict[str, Any]]:
    """Detect if user is requesting information about a specific lesson.
    
    Examples:
    - "Tell me about lesson 10"
    - "What is lesson 5?"
    - "Explain lesson 42"
    
    Args:
        text: User's message text
        
    Returns:
        Dict with lesson_id if detected, None otherwise
    """
    return _detect_lesson_request(text)


def get_current_lesson_state(
    user_id: int,
    memory_manager: MemoryManager,
) -> Dict[str, Any]:
    """Get the current lesson state for a user.
    
    Args:
        user_id: User ID
        memory_manager: Memory manager instance
        
    Returns:
        Dict containing current_lesson and last_sent_lesson_id
    """
    return _get_lesson_state(memory_manager, user_id)


def get_current_lesson(
    memory_manager: MemoryManager,
    user_id: int,
) -> Optional[Any]:
    """Get the current lesson for a user.
    
    Args:
        memory_manager: Memory manager instance
        user_id: User ID
        
    Returns:
        Current lesson ID (int or "continuing") or None
    """
    return _get_current_lesson(memory_manager, user_id)


def set_current_lesson(
    memory_manager: MemoryManager,
    user_id: int,
    lesson_id: Any,
) -> None:
    """Set the current lesson for a user.
    
    Args:
        memory_manager: Memory manager instance
        user_id: User ID
        lesson_id: Lesson ID (int or "continuing")
    """
    _set_current_lesson(memory_manager, user_id, lesson_id, write_legacy=True)


def get_last_sent_lesson_id(
    memory_manager: MemoryManager,
    user_id: int,
) -> Optional[int]:
    """Get the last sent lesson ID for a user.
    
    Args:
        memory_manager: Memory manager instance
        user_id: User ID
        
    Returns:
        Last sent lesson ID or None
    """
    return _get_last_sent_lesson_id(memory_manager, user_id)


def set_last_sent_lesson_id(
    memory_manager: MemoryManager,
    user_id: int,
    lesson_id: int,
) -> None:
    """Set the last sent lesson ID for a user.
    
    Args:
        memory_manager: Memory manager instance
        user_id: User ID
        lesson_id: Lesson ID
    """
    _set_last_sent_lesson_id(memory_manager, user_id, lesson_id, write_legacy=True)


def has_lesson_status(
    memory_manager: MemoryManager,
    user_id: int,
) -> bool:
    """Check if user has any lesson-related progress info.
    
    Args:
        memory_manager: Memory manager instance
        user_id: User ID
        
    Returns:
        True if user has lesson status
    """
    return _has_lesson_status(memory_manager, user_id)


def compute_current_lesson_state(
    memory_manager: MemoryManager,
    user_id: int,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Compute the lesson state for determining "today's" lesson.
    
    Args:
        memory_manager: Memory manager instance
        user_id: User ID
        today: Optional date for testing (defaults to UTC today)
        
    Returns:
        Dict with lesson_id, progress_note, advanced_by_day, etc.
    """
    return _compute_current_lesson_state(memory_manager, user_id, today)


async def process_lesson_query(
    user_id: int,
    text: str,
    session: Session,
    prompt_builder: Optional[Any] = None,
    memory_manager: Optional[MemoryManager] = None,
    onboarding_flow: Optional[Any] = None,
    onboarding_service: Optional[Any] = None,
    user_language: Optional[str] = None,
) -> Optional[str]:
    """Process a lesson-related query from a user.
    
    Args:
        user_id: User ID
        text: User's message
        session: Database session
        prompt_builder: Optional prompt builder
        memory_manager: Optional memory manager
        onboarding_flow: Optional onboarding flow handler
        onboarding_service: Optional onboarding service
        user_language: User's language
        
    Returns:
        Response string if handled, None otherwise
    """
    return await _process_lesson_query(
        user_id=user_id,
        text=text,
        session=session,
        prompt_builder=prompt_builder,
        memory_manager=memory_manager,
        onboarding_flow=onboarding_flow,
        onboarding_service=onboarding_service,
        user_language=user_language,
    )


async def maybe_send_next_lesson(
    user_id: int,
    text: str,
    session: Session,
    prompt_builder: Any,
    memory_manager: MemoryManager,
    call_ollama: Any,
) -> Optional[str]:
    """Check if we should auto-send the next lesson on a new day.
    
    Args:
        user_id: User ID
        text: User's message
        session: Database session
        prompt_builder: Prompt builder instance
        memory_manager: Memory manager instance
        call_ollama: Function to call Ollama
        
    Returns:
        Lesson message if sent, None otherwise
    """
    return await _maybe_send_next_lesson(
        user_id=user_id,
        text=text,
        session=session,
        prompt_builder=prompt_builder,
        memory_manager=memory_manager,
        call_ollama=call_ollama,
    )


def apply_reported_progress(
    memory_manager: MemoryManager,
    user_id: int,
    lesson_id: int,
) -> None:
    """Apply reported progress to lesson state.
    
    Args:
        memory_manager: Memory manager instance
        user_id: User ID
        lesson_id: Reported lesson ID
    """
    _apply_reported_progress(memory_manager, user_id, lesson_id)


# Re-export types for convenience
__all__ = [
    "get_lesson",
    "format_lesson_message",
    "deliver_lesson",
    "detect_lesson_request",
    "get_current_lesson_state",
    "get_current_lesson",
    "set_current_lesson",
    "get_last_sent_lesson_id",
    "set_last_sent_lesson_id",
    "has_lesson_status",
    "compute_current_lesson_state",
    "process_lesson_query",
    "maybe_send_next_lesson",
    "apply_reported_progress",
]
