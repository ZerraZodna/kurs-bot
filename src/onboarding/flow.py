from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session
from src.services.gdpr_service import record_consent
from src.onboarding.user_management import delete_user_and_data
from src.memories.dialogue_helpers import get_user_language
from src.memories.constants import MemoryCategory, MemoryKey
from src.language import onboarding_prompts as prompts_module
from src.language.onboarding_prompts import format_onboarding_message_with_name

logger = logging.getLogger(__name__)

# Sentinel value to indicate AI processing is needed for onboarding responses
NEEDS_AI_PROCESSING = "NEEDS_AI_PROCESSING"


class OnboardingStep(Enum):
    CONSENT = "consent"

class OnboardingFlow:
    def __init__(self, memory_manager, onboarding_service, call_ollama):
        self.memory_manager = memory_manager
        self.onboarding = onboarding_service
        self.call_ollama = call_ollama

    def _get_pending_step(self, user_id: int) -> Optional[str]:
        pending_step = self.memory_manager.get_memory(user_id, MemoryKey.ONBOARDING_STEP_PENDING)
        # Debug trace
        logger.debug(f"_get_pending_step - user_id={user_id} -> {pending_step}")
        if pending_step:
            return str(pending_step[0].get("value", "")).lower()
        return None

    def _resolve_pending_step(self, user_id: int):
        self.memory_manager.store_memory(
            user_id=user_id,
            key=MemoryKey.ONBOARDING_STEP_PENDING,
            value="resolved",
            category=MemoryCategory.CONVERSATION.value,
            ttl_hours=0.1,
            source="dialogue_engine",
            allow_duplicates=False,
        )
        logger.debug(f"_resolve_pending_step - user_id={user_id}")

    def _set_pending_lesson_delivery(self, user_id: int, lesson_id: str = ""):
        ttl_hours = 0.1 if lesson_id == "" else 1
        self.memory_manager.store_memory(
            user_id=user_id,
            key=MemoryKey.PENDING_LESSON_DELIVERY,
            value=lesson_id,
            category=MemoryCategory.CONVERSATION.value,
            ttl_hours=ttl_hours,
            source="dialogue_engine",
            allow_duplicates=False,
        )
        # set_current_lesson already handles lesson tracking

    def _store_memory(
        self,
        user_id: int,
        key: str,
        value: str,
        category: str = MemoryCategory.CONVERSATION.value,
        source: str = "dialogue_engine",
        ttl_hours: Optional[float] = None,
    ):
        self.memory_manager.store_memory(
            user_id=user_id,
            key=key,
            value=value,
            category=category,
            source=source,
            ttl_hours=ttl_hours,
            allow_duplicates=False,
        )
        logger.debug(f"_store_memory - user_id={user_id} key={key} value={value} category={category} ttl={ttl_hours}")

    def _get_message(self, key: str, language: str = "en") -> str:
        # Delegate prompt retrieval to prompts.py (centralized prompts)
        # The helper normalizes language codes; callers can format the returned
        # template (e.g. fill `{name}`) when needed.
        return prompts_module.get_onboarding_message(key, language)

    def _get_user_name(self, user_id: int) -> str:
        # Use topic-based retrieval for temporal resolution (newest name wins)
        name = self.memory_manager.topic_manager.get_name(user_id)
        logger.debug(f"_get_user_name - user_id={user_id} -> {name}")
        return name

    def _handle_declined(self, status: dict) -> Optional[str]:
        if status.get("declined_consent"):
            return None
        return None

    def _handle_consent_pending(self, user_id: int, text: str, session: Session) -> Optional[str]:
        logger.debug(f"_handle_consent_pending - user_id={user_id} text={text}")
        consent = self.onboarding.detect_consent_keywords(text)
        if consent is True:
            self._store_memory(user_id, MemoryKey.DATA_CONSENT, "granted", category=MemoryCategory.PROFILE.value)
            record_consent(session, user_id, "data_storage", True, "dialogue_engine_consent")
            self._resolve_pending_step(user_id)
            # Onboarding complete - return thank you + completion message
            language = get_user_language(self.memory_manager, user_id)
            logger.debug(f"consent granted - user_id={user_id} language={language}")
            thank_you = self._get_message("consent_granted", language)
            completion = self.onboarding.get_onboarding_complete_message(user_id)
            return f"{thank_you}\n\n{completion}"
        elif consent is False:
            self._store_memory(user_id, MemoryKey.DATA_CONSENT, "declined", category=MemoryCategory.PROFILE.value)
            record_consent(session, user_id, "data_storage", False, "dialogue_engine_consent")
            delete_user_and_data(session, user_id)
            self._resolve_pending_step(user_id)
            return self._get_message("consent_declined")
        return None

    async def handle_onboarding(self, user_id: int, text: str, session: Session) -> Optional[str]:
        """
        Handle onboarding flow.

        Simplified onboarding: only requires consent.
        - Name is now skipped - using Telegram name from DB
        - Consent is asked immediately for new users
        - Onboarding completes after consent is given
        
        Returns:
            Onboarding response or None if not in onboarding flow
        """
        status = self.onboarding.get_onboarding_status(user_id)
        logger.debug(f"handle_onboarding - user_id={user_id} text={text} status={status}")

        # Check if there's a pending step that needs processing
        pending_step = self._get_pending_step(user_id)
        logger.debug(f"handle_onboarding - user_id={user_id} pending_step={pending_step}")

        # If there's a pending consent step, process the user's answer
        if pending_step == "consent":
            # Process user's response to the consent question
            consent_response = self._handle_consent_pending(user_id, text, session)
            if consent_response:
                # Consent was granted or declined - return the response
                return consent_response
            # If consent_response is None, the answer was unclear - ask again
            # Fall through to ask consent again

        # Skip name check - using Telegram name from DB
        # Only check for consent
        if not status.get("has_consent"):
            language = get_user_language(self.memory_manager, user_id)
            # Only store pending step if there wasn't one already
            if pending_step != "consent":
                self._store_memory(user_id, MemoryKey.ONBOARDING_STEP_PENDING, "consent", ttl_hours=2)
            logger.debug(f"asking for consent (no consent) user_id={user_id} language={language}")
            # Get personalized consent prompt with user's name
            name = self._get_user_name(user_id)
            consent_prompt = self._get_message("consent_prompt", language)
            return format_onboarding_message_with_name(consent_prompt, name)

        # Handle declined consent case
        if status.get("declined_consent"):
            return None

        # Onboarding complete - return None to let normal dialogue continue
        if status["onboarding_complete"]:
            return None

        # Return next onboarding prompt (should not reach here with simplified flow)
        return self.onboarding.get_onboarding_prompt(user_id)

