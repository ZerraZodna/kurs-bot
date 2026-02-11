"""
Onboarding Service - Guide users through setup and commitment

Delegates to helper modules for:
- Status checking
- Prompt generation
- Detector logic
- Schedule setup
- User management
"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from src.services.memory_manager import MemoryManager
import logging

from src.services.onboarding.detectors import (
    detect_commitment_keywords,
    detect_consent_keywords,
    detect_decline_keywords,
    detect_schedule_request,
    handle_lesson_status_response,
)
from src.services.onboarding.prompts import (
    get_continuation_welcome_message,
    get_lesson_1_welcome_message,
    get_onboarding_complete_message_text,
    get_onboarding_prompts,
)
from src.services.onboarding.status import get_onboarding_status_dict
from src.services.onboarding.schedule_setup import create_auto_schedule
from src.services.timezone_utils import ensure_user_timezone
from src.services.onboarding.user_management import delete_user_and_data, is_user_new

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
        commitment_memories = self.memory_manager.get_memory(user_id, "acim_commitment")
        has_commitment = bool(commitment_memories)
        declined_commitment = any(
            str(m.get("value", "")).lower() in ["declined", "no", "not interested"]
            for m in commitment_memories
        )

        first_name_memories = self.memory_manager.get_memory(user_id, "first_name")
        name_memories = self.memory_manager.get_memory(user_id, "name")
        has_name = bool(first_name_memories or name_memories)

        # Migrate name if needed
        if name_memories and not first_name_memories:
            self.memory_manager.store_memory(
                user_id=user_id,
                key="first_name",
                value=name_memories[0].get("value"),
                confidence=name_memories[0].get("confidence", 1.0),
                source="onboarding_service_name_migration",
                category="profile",
            )

        consent_memories = self.memory_manager.get_memory(user_id, "data_consent")
        has_consent = bool(consent_memories)
        declined_consent = any(
            str(m.get("value", "")).lower() in ["declined", "no", "not consent"]
            for m in consent_memories
        )

        lesson_status_memories = self.memory_manager.get_memory(user_id, "current_lesson")
        has_lesson_status = bool(lesson_status_memories)

        return get_onboarding_status_dict(
            has_name=has_name,
            has_consent=has_consent,
            has_commitment=has_commitment,
            has_lesson_status=has_lesson_status,
            declined_commitment=declined_commitment,
            declined_consent=declined_consent,
        )
    
    def get_onboarding_prompt(self, user_id: int) -> Optional[str]:
        """Get the next onboarding prompt for the user in their language."""
        status = self.get_onboarding_status(user_id)

        if status["onboarding_complete"]:
            return None

        lang_memories = self.memory_manager.get_memory(user_id, "user_language")
        language = lang_memories[0]["value"] if lang_memories else "en"

        next_step = status["next_step"]
        name_memories = self.memory_manager.get_memory(user_id, "first_name")
        if not name_memories:
            name_memories = self.memory_manager.get_memory(user_id, "name")
        name = name_memories[0]["value"] if name_memories else "friend"

        lang_prompts = get_onboarding_prompts(language, name)

        if next_step == "name":
            self.memory_manager.store_memory(
                user_id=user_id,
                key="onboarding_step_pending",
                value="name",
                category="conversation",
                ttl_hours=2,
                source="onboarding_service",
                allow_duplicates=False,
            )
            return lang_prompts["name"]
        elif next_step == "consent":
            self.memory_manager.store_memory(
                user_id=user_id,
                key="onboarding_step_pending",
                value="consent",
                category="conversation",
                ttl_hours=2,
                source="onboarding_service",
                allow_duplicates=False,
            )
            return lang_prompts["consent"]
        elif next_step == "commitment":
            self.memory_manager.store_memory(
                user_id=user_id,
                key="onboarding_step_pending",
                value="commitment",
                category="conversation",
                ttl_hours=2,
                source="onboarding_service",
                allow_duplicates=False,
            )
            return lang_prompts["commitment"]
        elif next_step == "lesson_status":
            self.memory_manager.store_memory(
                user_id=user_id,
                key="onboarding_step_pending",
                value="lesson_status",
                category="conversation",
                ttl_hours=2,
                source="onboarding_service",
                allow_duplicates=False,
            )
            return lang_prompts["lesson_status"]

        return None
    
    def get_onboarding_complete_message(self, user_id: int) -> str:
        """
        Get the completion message after onboarding is done.
        Also automatically creates a daily schedule at 07:30 AM.
        """
        name_memories = self.memory_manager.get_memory(user_id, "first_name")
        if not name_memories:
            name_memories = self.memory_manager.get_memory(user_id, "name")
        name = name_memories[0]["value"] if name_memories else "friend"

        lang_memories = self.memory_manager.get_memory(user_id, "user_language")
        language = lang_memories[0]["value"] if lang_memories else "en"

        ensure_user_timezone(self.memory_manager, user_id, language)

        # Auto-create schedule
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
        
        Returns:
            Dict with action: "send_lesson_1" or "ask_lesson_number" and appropriate message
        """
        return handle_lesson_status_response(text)

    def get_lesson_1_welcome_message(self, user_id: int) -> str:
        """Welcome message for brand new users starting with Lesson 1."""
        name_memories = self.memory_manager.get_memory(user_id, "first_name")
        if not name_memories:
            name_memories = self.memory_manager.get_memory(user_id, "name")
        name = name_memories[0]["value"] if name_memories else "friend"

        lang_memories = self.memory_manager.get_memory(user_id, "user_language")
        language = lang_memories[0]["value"] if lang_memories else "en"

        return get_lesson_1_welcome_message(language, name)

    def get_continuation_welcome_message(self, user_id: int, lesson_id: int) -> str:
        """Welcome message for users continuing from a specific lesson."""
        name_memories = self.memory_manager.get_memory(user_id, "first_name")
        if not name_memories:
            name_memories = self.memory_manager.get_memory(user_id, "name")
        name = name_memories[0]["value"] if name_memories else "friend"

        lang_memories = self.memory_manager.get_memory(user_id, "user_language")
        language = lang_memories[0]["value"] if lang_memories else "en"

        return get_continuation_welcome_message(language, name, lesson_id)
