"""Onboarding service - guide users through setup.

Provides the `OnboardingService` implementation that coordinates
detectors, prompt generation, schedule setup, and user management.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.language.onboarding_prompts import (
    format_onboarding_message_with_name,
    get_continuation_welcome_message,
    get_lesson_1_welcome_message,
    get_onboarding_complete_message_text,
    get_onboarding_message,
)
from src.memories import MemoryManager
from src.memories.constants import MemoryCategory, MemoryKey
from src.onboarding.detectors import (
    detect_consent_keywords,
    detect_decline_keywords,
)
from src.onboarding.schedule_setup import create_auto_schedule
from src.onboarding.status import get_onboarding_status_dict
from src.onboarding.user_management import is_user_new

logger = logging.getLogger(__name__)


class OnboardingService:
    """Manages user onboarding flow"""

    def __init__(self, db: Session):
        self.db = db
        self.memory_manager = MemoryManager(db)

    def get_onboarding_status(self, user_id: int) -> Dict[str, Any]:
        """
        Check user's onboarding completion status.

        Returns:
            Dict with onboarding_complete, steps_completed, next_step
        
        Note: Name is now always considered complete - using Telegram name from DB.
        """
        # Name is now automatically considered complete (using Telegram name from DB)
        # We still check memory in case user explicitly set a different name

        consent_memories = self.memory_manager.get_memory(user_id, MemoryKey.DATA_CONSENT)
        has_consent = bool(consent_memories)
        declined_consent = any(
            str(m.get("value", "")).lower() in ["declined", "no", "not consent"]
            for m in consent_memories
        )

        # Pass has_consent first (required arg), has_name uses default (True)
        return get_onboarding_status_dict(
            has_consent=has_consent,
            declined_consent=declined_consent,
        )
    
    def get_onboarding_prompt(self, user_id: int) -> Optional[str]:
        """Get the next onboarding prompt for the user in their language."""
        status = self.get_onboarding_status(user_id)

        if status["onboarding_complete"]:
            return None

        lang_memories = self.memory_manager.get_memory(user_id, MemoryKey.USER_LANGUAGE)
        language = lang_memories[0]["value"] if lang_memories else "en"

        next_step = status["next_step"]
        
        # Only handle consent step - name is skipped (using Telegram name from DB)
        if next_step == "consent":
            self.memory_manager.store_memory(
                user_id=user_id,
                key=MemoryKey.ONBOARDING_STEP_PENDING,
                value="consent",
                category=MemoryCategory.CONVERSATION.value,
                ttl_hours=2,
                source="onboarding_service",
                allow_duplicates=False,
            )
            # Get personalized consent prompt with user's name
            consent_prompt = get_onboarding_message("consent_prompt", language)
            name = self.memory_manager.topic_manager.get_name(user_id)
            return format_onboarding_message_with_name(consent_prompt, name)
        
        # If somehow we get "name" as next_step, just skip it and return consent
        # This shouldn't happen with the new logic, but just in case
        if next_step == "name":
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
        
        return None
    
    def get_onboarding_complete_message(self, user_id: int) -> str:
        """
        Finalize onboarding side-effects (schedule) and return
        the onboarding completion message text for the user.
        """
        # Use topic-based name retrieval for temporal resolution
        name = self.memory_manager.topic_manager.get_name(user_id)

        lang_memories = self.memory_manager.get_memory(user_id, MemoryKey.USER_LANGUAGE)
        language = lang_memories[0]["value"] if lang_memories else "en"

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
            if status.get("declined_consent"):
                return False
            return True
        
        return False
    
    def detect_decline_keywords(self, message: str) -> bool:
        """Detect if user declines ACIM or consent."""
        return detect_decline_keywords(message)

    def detect_consent_keywords(self, message: str) -> Optional[bool]:
        """Return True if consent given, False if declined, None if unclear."""
        return detect_consent_keywords(message)
    
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
