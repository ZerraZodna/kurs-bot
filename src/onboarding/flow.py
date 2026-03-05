from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session
from src.models.database import User

from src.models.database import Lesson
from src.services.gdpr_service import record_consent
from src.lessons.api import format_lesson_message, set_current_lesson, get_current_lesson
from src.lessons.handler import translate_text
from src.onboarding.user_management import delete_user_and_data
from src.memories.dialogue_helpers import get_user_language
from src.memories.constants import MemoryCategory, MemoryKey
from src.language import onboarding_prompts as prompts_module

logger = logging.getLogger(__name__)

# Sentinel value to indicate AI processing is needed for onboarding responses
NEEDS_AI_PROCESSING = "NEEDS_AI_PROCESSING"


class OnboardingStep(Enum):
    NAME = "name"
    CONSENT = "consent"
    # Removed: TIMEZONE, COMMITMENT, LESSON_STATUS, INTRO_OFFER - simplified to name + consent only


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
        confidence: float = 1.0,
        source: str = "dialogue_engine",
        ttl_hours: Optional[float] = None,
    ):
        self.memory_manager.store_memory(
            user_id=user_id,
            key=key,
            value=value,
            category=category,
            confidence=confidence,
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

    async def _handle_pending_step(self, user_id: int, text: str, session: Session, step: str) -> Optional[str]:
        if step == OnboardingStep.CONSENT.value:
            return self._handle_consent_pending(user_id, text, session)
        elif step == OnboardingStep.NAME.value:
            return await self._handle_name_pending(user_id, text, session)
        # Removed: TIMEZONE, COMMITMENT, LESSON_STATUS, INTRO_OFFER handlers
        return None

    async def _handle_name_pending(self, user_id: int, text: str, session: Session) -> Optional[str]:
        """Handle the pending 'name' step.

        Expected behaviour:
        - If user confirms (yes), store the Telegram first_name from DB as `first_name` memory.
        - If user replies with a name, store that as `first_name` memory.
        - If user explicitly declines, ask what they prefer to be called.
        After storing the preferred name, continue onboarding (next prompt from service).
        """
        logger.debug(f"_handle_name_pending - user_id={user_id} text={text}")
        t = (text or "").strip()
        lname = t.lower()

        # simple affirmative/negative detection
        affirmatives = {"yes", "y", "sure", "ok", "okay", "ja", "yea", "yep", "sure!", "ok!"}
        negatives = {"no", "n", "don't", "dont", "nope", "nei"}

        # If user confirms, use DB user first_name if present
        if lname in affirmatives:
            try:
                db_user = session.query(User).filter(User.user_id == user_id).first()
                if db_user and db_user.first_name:
                    self._store_memory(user_id, MemoryKey.FIRST_NAME, db_user.first_name, category=MemoryCategory.PROFILE.value)
                    self._resolve_pending_step(user_id)
                    return self.onboarding.get_onboarding_prompt(user_id)
            except Exception:
                pass
            # fallback: ask for name explicitly
            self._store_memory(user_id, MemoryKey.ONBOARDING_STEP_PENDING, OnboardingStep.NAME.value, ttl_hours=2)
            language = get_user_language(self.memory_manager, user_id)
            if language == "no":
                return "Hva vil du at jeg skal kalle deg?"
            return "What would you like me to call you?"

        if lname in negatives:
            # user declined — ask for preferred name explicitly
            self._store_memory(user_id, MemoryKey.ONBOARDING_STEP_PENDING, OnboardingStep.NAME.value, ttl_hours=2)
            language = get_user_language(self.memory_manager, user_id)
            if language == "no":
                return "Hva vil du at jeg skal kalle deg?"
            return "What would you like me to call you?"

        # Otherwise, treat the reply as the preferred name and store it
        preferred = t
        if preferred:
            self._store_memory(user_id, MemoryKey.FIRST_NAME, preferred, category=MemoryCategory.PROFILE.value)
            self._resolve_pending_step(user_id)
            return self.onboarding.get_onboarding_prompt(user_id)

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

        Simplified onboarding: only requires name + consent.
        - Name is asked first (or use Telegram name if available)
        - Consent is asked after name
        - Onboarding completes after consent is given
        
        Returns:
            Onboarding response or None if not in onboarding flow
        """
        status = self.onboarding.get_onboarding_status(user_id)
        logger.debug(f"handle_onboarding - user_id={user_id} text={text} status={status}")

        # If there is a pending onboarding step, handle it first so replies
        # to prompts (e.g. consent "yes") are processed instead of re-asking.
        pending_step = self._get_pending_step(user_id)
        if pending_step:
            logger.debug(f"pending_step detected: {pending_step} for user {user_id}")
            response = await self._handle_pending_step(user_id, text, session, pending_step)
            if response:
                return response
            self._resolve_pending_step(user_id)

        # If no name info exists, delegate to the onboarding service which
        # may prefer to ask permission to use an existing Telegram `first_name`.
        if not status.get("has_name"):
            logger.debug(f"asking for name (no name) delegating to service user_id={user_id}")
            return self.onboarding.get_onboarding_prompt(user_id)

        # If no consent, ask for consent
        if not status.get("has_consent"):
            language = get_user_language(self.memory_manager, user_id)
            self._store_memory(user_id, MemoryKey.ONBOARDING_STEP_PENDING, "consent", ttl_hours=2)
            logger.debug(f"asking for consent (no consent) user_id={user_id} language={language}")
            return self._get_message("consent_prompt", language)

        # Handle declined consent case
        if status.get("declined_consent"):
            return None

        # Onboarding complete - return None to let normal dialogue continue
        if status["onboarding_complete"]:
            return None

        # Return next onboarding prompt (should not reach here with simplified flow)
        return self.onboarding.get_onboarding_prompt(user_id)

