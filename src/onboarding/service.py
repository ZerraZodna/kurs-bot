"""Onboarding service - guide users through setup and commitment.

Provides the `OnboardingService` implementation that coordinates
detectors, prompt generation, schedule setup, and user management.
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from src.memories import MemoryManager
import logging

from src.onboarding.detectors import (
    detect_commitment_keywords,
    detect_consent_keywords,
    detect_decline_keywords,
    detect_schedule_request,
    handle_lesson_status_response,
)
from src.language.onboarding_prompts import (
    get_continuation_welcome_message,
    get_lesson_1_welcome_message,
    get_onboarding_complete_message_text,
    get_onboarding_message,
)
from src.models.database import User
from src.onboarding.status import get_onboarding_status_dict
from src.onboarding.schedule_setup import create_auto_schedule
from src.core.timezone import ensure_user_timezone
from src.onboarding.user_management import delete_user_and_data, is_user_new
from src.lessons.state import set_current_lesson, get_lesson_state, has_lesson_status
from src.memories.constants import MemoryCategory, MemoryKey

logger = logging.getLogger(__name__)


class OnboardingService:
    """Manages user onboarding flow and commitment tracking."""

    def __init__(self, db: Session):
        self.db = db
        self.memory_manager = MemoryManager(db)

    def get_onboarding_status(self, user_id: int) -> Dict[str, Any]:
        """
        Check user's onboarding completion status.

        Returns:
            Dict with onboarding_complete, steps_completed, next_step
        """
        commitment_memories = self.memory_manager.get_memory(user_id, MemoryKey.ACIM_COMMITMENT)
        has_commitment = bool(commitment_memories)
        declined_commitment = any(
            str(m.get("value", "")).lower() in ["declined", "no", "not interested"]
            for m in commitment_memories
        )

        # Use topic-based name retrieval for temporal resolution
        name = self.memory_manager.topic_manager.get_name(user_id)
        has_name = name != "friend"

        consent_memories = self.memory_manager.get_memory(user_id, MemoryKey.DATA_CONSENT)
        has_consent = bool(consent_memories)
        declined_consent = any(
            str(m.get("value", "")).lower() in ["declined", "no", "not consent"]
            for m in consent_memories
        )

        # Use consolidated lesson_state helper for onboarding status
        lesson_status_present = has_lesson_status(self.memory_manager, user_id)

        return get_onboarding_status_dict(
            has_name=has_name,
            has_consent=has_consent,
            has_commitment=has_commitment,
            has_lesson_status=lesson_status_present,
            declined_commitment=declined_commitment,
            declined_consent=declined_consent,
        )
    
    def get_onboarding_prompt(self, user_id: int) -> Optional[str]:
        """Get the next onboarding prompt for the user in their language."""
        status = self.get_onboarding_status(user_id)

        if status["onboarding_complete"]:
            return None

        #language = get_user_language(self.memory_manager, user_id)
        lang_memories = self.memory_manager.get_memory(user_id, MemoryKey.USER_LANGUAGE)
        language = lang_memories[0]["value"] if lang_memories else "en"

        next_step = status["next_step"]
        # Use topic-based name retrieval for temporal resolution
        name = self.memory_manager.topic_manager.get_name(user_id)

        if next_step == "name":
            self.memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.ONBOARDING_STEP_PENDING,
                value="name",
                category=MemoryCategory.CONVERSATION.value,
                ttl_hours=2,
                source="onboarding_service",
                allow_duplicates=False,
            )
            # If we have a first/last name in the DB (from Telegram), prefer
            # asking permission to use that first name rather than asking for
            # the full name again. Re-use the `name_prompt` template and
            # format it with `first` and `full` placeholders. If no name is
            # available at all, fall back to a simple, generic "What's your
            # name?" question (don't return an unformatted template).
            first_name_memories = self.memory_manager.get_memory(user_id, MemoryKey.FIRST_NAME)
            last_name_memories = self.memory_manager.get_memory(user_id, MemoryKey.LAST_NAME)

            # Helper to format the template with available parts
            def _format_with(first: str, last: Optional[str] = None) -> str:
                full = f"{first} {last}".strip() if last else first
                return get_onboarding_message("name_prompt", language).format(first=first, full=full)

            # Prefer memory-stored names
            if first_name_memories:
                first = first_name_memories[0].get("value")
                # use last_name memory if present
                last = last_name_memories[0].get("value") if last_name_memories else None
                return _format_with(first, last)

            # Try to fetch from the users table as a fallback
            try:
                db_user = self.db.query(User).filter(User.user_id == user_id).first()
                if db_user and db_user.first_name:
                    return _format_with(db_user.first_name, db_user.last_name)
            except Exception:
                # If DB lookup fails, fall back to the generic prompt
                pass

            # No name available — return a generic localized prompt asking
            # for the user's name (do not attempt to format the template).
            if language == "no":
                return "Velkommen! Hva heter du? 👋"
            return "Welcome! What's your name? 👋"
        elif next_step == "consent":
            self.memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.ONBOARDING_STEP_PENDING,
                value="consent",
                category=MemoryCategory.CONVERSATION.value,
                ttl_hours=2,
                source="onboarding_service",
                allow_duplicates=False,
            )
            return get_onboarding_message("consent_prompt", language)
        elif next_step == "commitment":
            self.memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.ONBOARDING_STEP_PENDING,
                value="commitment",
                category=MemoryCategory.CONVERSATION.value,
                ttl_hours=2,
                source="onboarding_service",
                allow_duplicates=False,
            )
            # commitment prompt includes the user's name
            return get_onboarding_message("commitment_prompt", language).format(name=name)
        elif next_step == "lesson_status":
            self.memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.ONBOARDING_STEP_PENDING,
                value="lesson_status",
                category=MemoryCategory.CONVERSATION.value,
                ttl_hours=2,
                source="onboarding_service",
                allow_duplicates=False,
            )
            return get_onboarding_message("ask_new_or_continuing", language).format(name=name)

        return None
    
    def get_onboarding_complete_message(self, user_id: int) -> str:
        """
        Finalize onboarding side-effects (timezone, schedule) and return
        the onboarding completion message text for the user.
        """
        # Use topic-based name retrieval for temporal resolution
        name = self.memory_manager.topic_manager.get_name(user_id)

        lang_memories = self.memory_manager.get_memory(user_id, MemoryKey.USER_LANGUAGE)
        language = lang_memories[0]["value"] if lang_memories else "en"

        ensure_user_timezone(self.memory_manager, user_id, language)

        # Auto-create schedule when onboarding is completed
        create_auto_schedule(self.db, user_id)

        return get_onboarding_complete_message_text(language, name)
    
    def is_user_new(self, user_id: int) -> bool:
        """Check if user is new (created within last 10 minutes)."""
        return is_user_new(self.db, user_id)
    
    def should_show_onboarding(self, user_id: int) -> bool:
        """
        Determine if we should show onboarding prompts.
        
        Returns:
            True if user needs onboarding
        """
        pending_step = self.memory_manager.get_memory(user_id, MemoryKey.ONBOARDING_STEP_PENDING)
        if pending_step:
            val = str(pending_step[0].get("value", "")).lower().strip()
            if val and val != "resolved":
                return True

        status = self.get_onboarding_status(user_id)
        
        # Show if not complete and user is relatively new (or never completed)
        if not status["onboarding_complete"]:
            if status.get("declined_consent") or status.get("declined_commitment"):
                return False
            return True
        
        return False
    
    def detect_commitment_keywords(self, message: str) -> bool:
        """
        Detect if user message indicates readiness to commit to lessons.
        
        Args:
            message: Users message text
        
        Returns:
            True if commitment keywords detected
        """
        return detect_commitment_keywords(message)

    def detect_decline_keywords(self, message: str) -> bool:
        """Detect if user declines ACIM or consent."""
        return detect_decline_keywords(message)

    def detect_consent_keywords(self, message: str) -> Optional[bool]:
        """Return True if consent given, False if declined, None if unclear."""
        return detect_consent_keywords(message)
    
    def detect_schedule_request(self, message: str) -> bool:
        """
        Detect if user is asking for reminders/scheduling.
        
        Args:
            message: Users message text
        
        Returns:
            True if scheduling keywords detected
        """
        return detect_schedule_request(message)

    def handle_lesson_status_response(self, user_id: int, text: str) -> Dict[str, Any]:
        """
        Handle user's response about whether they're new or continuing.

        Uses the detectors' structured facts to store a `current_lesson` memory when
        an explicit lesson number is provided, and to avoid re-asking the 'new/continue'
        question when facts indicate the user is continuing or has completed the course.

        Returns the detector response dict for downstream handling.
        """
        result = handle_lesson_status_response(text)

        # Persist explicit lesson number so onboarding flow won't ask again
        try:
            action = result.get("action")
            facts = result.get("facts") or {}
        except Exception:
            action = None
            facts = {}

        if action == "send_specific_lesson":
            lesson_id = result.get("lesson_id")
            if lesson_id:
                # store as a progress memory so get_onboarding_status sees it
                # Use consolidated lesson_state helper to keep state consistent
                set_current_lesson(self.memory_manager, user_id, int(lesson_id))
        elif facts.get("is_continuing") or facts.get("completed_before"):
            # mark that user is continuing (no specific lesson known)
            set_current_lesson(self.memory_manager, user_id, "continuing")

        return result

    def get_lesson_1_welcome_message(self, user_id: int) -> str:
        """Welcome message for brand new users starting with Lesson 1."""
        # Use topic-based name retrieval for temporal resolution
        name = self.memory_manager.topic_manager.get_name(user_id)

        lang_memories = self.memory_manager.get_memory(user_id, MemoryKey.USER_LANGUAGE)
        language = lang_memories[0]["value"] if lang_memories else "en"

        return get_lesson_1_welcome_message(language, name)

    def get_continuation_welcome_message(self, user_id: int, lesson_id: int) -> str:
        """Welcome message for users continuing from a specific lesson."""
        # Use topic-based name retrieval for temporal resolution
        name = self.memory_manager.topic_manager.get_name(user_id)

        lang_memories = self.memory_manager.get_memory(user_id, MemoryKey.USER_LANGUAGE)
        language = lang_memories[0]["value"] if lang_memories else "en"

        return get_continuation_welcome_message(language, name, lesson_id)
__all__ = ["OnboardingService"]
