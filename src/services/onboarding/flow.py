from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session

from src.models.database import Lesson
from src.services.gdpr_service import record_consent
from src.services.dialogue.lesson_handler import format_lesson_message
from src.services.dialogue.memory_helpers import delete_user_and_data, get_user_language

logger = logging.getLogger(__name__)


class OnboardingStep(Enum):
    CONSENT = "consent"
    COMMITMENT = "commitment"
    LESSON_STATUS = "lesson_status"


MESSAGES = {
    "consent_declined": {
        "en": "Understood. I won't store your information. If you change your mind, just message me again.",
        "no": "Forstått. Jeg lagrer ikke informasjonen din. Hvis du ombestemmer deg, bare send meg en melding igjen.",
    },
    "commitment_declined": {
        "en": "Understood. I won't ask about ACIM lessons. If you want to resume later, just message me.",
        "no": "Forstått. Jeg spør ikke om ACIM-leksjoner. Hvis du vil fortsette senere, bare send meg en melding.",
    },
    "lesson_load_error": {
        "en": "I couldn't load that lesson right now. Please try again.",
        "no": "Jeg kunne ikke laste inn den leksjonen akkurat nå. Vennligst prøv igjen.",
    },
    "lesson_1_load_error": {
        "en": "I couldn't load Lesson 1 right now. Please try again.",
        "no": "Jeg kunne ikke laste inn Leksjon 1 akkurat nå. Vennligst prøv igjen.",
    },
    "ask_lesson_number": {
        "en": "Great! Which lesson are you currently working on?",
        "no": "Flott! Hvilken leksjon jobber du med nå?",
    },
    "ask_new_or_continuing": {
        "en": "Are you completely new to ACIM, or have you already started? (Answer 'new' or 'continuing')",
        "no": "Er du helt ny til ACIM, eller har du allerede begynt? (Svar 'ny' eller 'fortsetter')",
    },
    "name_prompt": {
        "en": "Welcome! I'm your spiritual coach for A Course in Miracles. What's your name?",
        "no": "Velkommen! Jeg er din åndelige veileder for A Course in Miracles. Hva heter du?",
    },
    "consent_prompt": {
        "en": "Before we continue: Do you consent to me storing the conversation and relevant info to support you? (yes/no)",
        "no": "Før vi fortsetter: Er det greit at jeg lagrer samtalen og relevant informasjon for å gi deg oppfølging? (ja/nei)",
    },
    "consent_granted": {
        "en": "Thank you for consenting to store your conversation data. This helps me provide better support.",
        "no": "Takk for at du samtykker til å lagre samtalen. Dette hjelper meg å gi deg bedre støtte.",
    },
    "commitment_prompt": {
        "en": "Beautiful, {name}!\nAre you interested in exploring these lessons together? I'm here to guide and support you on this journey.",
        "no": "Herlig, {name}!\nEr du interessert i å utforske disse leksjonene sammen med meg? Jeg er her for å veilede og støtte deg på denne reisen.",
    },
    "lesson_status_prompt": {
        "en": "Wonderful, {name}! Are you new to ACIM, or have you already begun working with the lessons?",
        "no": "Flott, {name}! Er du ny til ACIM, eller har du allerede begynt med leksjonene?",
    },
}


class OnboardingFlow:
    def __init__(self, memory_manager, onboarding_service, call_ollama):
        self.memory_manager = memory_manager
        self.onboarding = onboarding_service
        self.call_ollama = call_ollama

    def _get_pending_step(self, user_id: int) -> Optional[str]:
        pending_step = self.memory_manager.get_memory(user_id, "onboarding_step_pending")
        if pending_step:
            return str(pending_step[0].get("value", "")).lower()
        return None

    def _resolve_pending_step(self, user_id: int):
        self.memory_manager.store_memory(
            user_id=user_id,
            key="onboarding_step_pending",
            value="resolved",
            category="conversation",
            ttl_hours=0.1,
            source="dialogue_engine",
            allow_duplicates=False,
        )

    def _set_pending_lesson_delivery(self, user_id: int, lesson_id: str = ""):
        ttl_hours = 0.1 if lesson_id == "" else 1
        self.memory_manager.store_memory(
            user_id=user_id,
            key="pending_lesson_delivery",
            value=lesson_id,
            category="conversation",
            ttl_hours=ttl_hours,
            source="dialogue_engine",
            allow_duplicates=False,
        )

    def _store_memory(self, user_id: int, key: str, value: str, category: str = "conversation", confidence: float = 1.0, source: str = "dialogue_engine", ttl_hours: Optional[float] = None):
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

    def _get_message(self, key: str, language: str = "en") -> str:
        # Normalize full-language names (e.g. 'Norwegian', 'English') to short codes used in MESSAGES
        lang_key = language
        if isinstance(language, str):
            lname = language.lower()
            if lname in ("norwegian", "nb", "nn"):
                lang_key = "no"
            elif lname in ("english", "en"):
                lang_key = "en"
            elif lname in ("swedish", "sv"):
                lang_key = "sv"
            elif lname in ("danish", "da"):
                lang_key = "da"
            elif lname in ("german", "de"):
                lang_key = "de"
            else:
                # leave as-is (may already be a short code)
                lang_key = language

        return MESSAGES.get(key, {}).get(lang_key, MESSAGES[key]["en"])

    def _get_user_name(self, user_id: int) -> str:
        name_memories = self.memory_manager.get_memory(user_id, "first_name")
        if not name_memories:
            name_memories = self.memory_manager.get_memory(user_id, "name")
        return name_memories[0]["value"] if name_memories else "friend"

    def _get_commitment_prompt(self, language: str, name: str) -> str:
        prompt = self._get_message("commitment_prompt", language)
        return prompt.format(name=name)

    def _get_lesson_status_prompt(self, language: str, name: str) -> str:
        prompt = self._get_message("lesson_status_prompt", language)
        return prompt.format(name=name)

    def _handle_declined(self, status: dict) -> Optional[str]:
        if status.get("declined_consent"):
            return None
        if status.get("declined_commitment"):
            return self._get_message("commitment_declined")
        return None

    async def _handle_pending_step(self, user_id: int, text: str, session: Session, step: str) -> Optional[str]:
        if step == OnboardingStep.CONSENT.value:
            return self._handle_consent_pending(user_id, text, session)
        elif step == OnboardingStep.COMMITMENT.value:
            return self._handle_commitment_pending(user_id, text)
        elif step == OnboardingStep.LESSON_STATUS.value:
            return await self._handle_lesson_status_pending(user_id, text, session)
        return None

    def _handle_consent_pending(self, user_id: int, text: str, session: Session) -> Optional[str]:
        consent = self.onboarding.detect_consent_keywords(text)
        if consent is True:
            self._store_memory(user_id, "data_consent", "granted", category="profile")
            record_consent(session, user_id, "data_storage", True, "dialogue_engine_consent")
            self._resolve_pending_step(user_id)
            # Return a localized thank-you and continue onboarding flow
            language = get_user_language(self.memory_manager, user_id)
            thank_you = self._get_message("consent_granted", language)
            next_prompt = self.onboarding.get_onboarding_prompt(user_id)
            if next_prompt:
                return f"{thank_you}\n\n{next_prompt}"
            return thank_you
        elif consent is False:
            self._store_memory(user_id, "data_consent", "declined", category="profile")
            record_consent(session, user_id, "data_storage", False, "dialogue_engine_consent")
            delete_user_and_data(session, user_id)
            self._resolve_pending_step(user_id)
            return self._get_message("consent_declined")
        return None

    def _handle_commitment_pending(self, user_id: int, text: str) -> Optional[str]:
        if self.onboarding.detect_decline_keywords(text):
            self._store_memory(user_id, "acim_commitment", "declined", category="goals")
            return self._get_message("commitment_declined")
        if self.onboarding.detect_commitment_keywords(text):
            self._store_memory(user_id, "acim_commitment", "committed to ACIM lessons", category="goals")
            return self.onboarding.get_onboarding_prompt(user_id)
        return None

    async def _handle_lesson_status_pending(self, user_id: int, text: str, session: Session) -> Optional[str]:
        response = self.onboarding.handle_lesson_status_response(user_id, text)
        action = response.get("action")

        if action == "send_lesson_1":
            return await self._deliver_lesson(user_id, 1, session, is_first=True)
        elif action == "send_specific_lesson":
            lesson_id = response["lesson_id"]
            return await self._deliver_lesson(user_id, lesson_id, session, is_first=False)
        elif action == "ask_lesson_number":
            language = get_user_language(self.memory_manager, user_id)
            self._store_memory(user_id, "onboarding_step_pending", OnboardingStep.LESSON_STATUS.value, ttl_hours=2)
            return self._get_message("ask_lesson_number", language)

        language = get_user_language(self.memory_manager, user_id)
        self._store_memory(user_id, "onboarding_step_pending", OnboardingStep.LESSON_STATUS.value, ttl_hours=2)
        return self._get_message("ask_new_or_continuing", language)

    async def _deliver_lesson(self, user_id: int, lesson_id: int, session: Session, is_first: bool) -> str:
        self._store_memory(user_id, "current_lesson", str(lesson_id), category="progress")

        completion_msg = self._check_and_send_completion_message(user_id)

        lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
        if not lesson:
            return self._get_message("lesson_1_load_error" if lesson_id == 1 else "lesson_load_error")

        language = get_user_language(self.memory_manager, user_id)
        if is_first:
            welcome_msg = self.onboarding.get_lesson_1_welcome_message(user_id)
        else:
            welcome_msg = self.onboarding.get_continuation_welcome_message(user_id, lesson_id)

        lesson_msg = await format_lesson_message(lesson, language, self.call_ollama)
        self._set_pending_lesson_delivery(user_id)
        self._resolve_pending_step(user_id)

        return f"{welcome_msg}\n\n{lesson_msg}"

    def _check_and_send_completion_message(self, user_id: int) -> Optional[str]:
        completion_sent = self.memory_manager.get_memory(user_id, "onboarding_complete_message_sent")
        if completion_sent:
            return None

        status = self.onboarding.get_onboarding_status(user_id)
        if status.get("has_name") and status.get("has_consent") and status.get("has_commitment"):
            self._store_memory(user_id, "onboarding_complete_message_sent", "true", ttl_hours=365 * 24)
            return self.onboarding.get_onboarding_complete_message(user_id)
        return None

    async def handle_onboarding(self, user_id: int, text: str, session: Session) -> Optional[str]:
        """
        Handle onboarding flow.

        Onboarding just collects basic info (name, commitment).
        
        Returns:
            Onboarding response or None if not in onboarding flow
        """
        status = self.onboarding.get_onboarding_status(user_id)

        # If there is a pending onboarding step, handle it first so replies
        # to prompts (e.g. consent "yes") are processed instead of re-asking.
        pending_step = self._get_pending_step(user_id)
        if pending_step:
            response = await self._handle_pending_step(user_id, text, session, pending_step)
            if response:
                return response
            self._resolve_pending_step(user_id)

        # If no name info exists, ask for name directly
        if not status.get("has_name"):
            language = get_user_language(self.memory_manager, user_id)
            self._store_memory(user_id, "onboarding_step_pending", "name", ttl_hours=2)
            return self._get_message("name_prompt", language)

        # If no consent, ask for consent
        if not status.get("has_consent"):
            language = get_user_language(self.memory_manager, user_id)
            self._store_memory(user_id, "onboarding_step_pending", "consent", ttl_hours=2)
            return self._get_message("consent_prompt", language)

        # If no commitment, ask for commitment
        if not status.get("has_commitment"):
            language = get_user_language(self.memory_manager, user_id)
            name = self._get_user_name(user_id)
            self._store_memory(user_id, "onboarding_step_pending", "commitment", ttl_hours=2)
            return self._get_commitment_prompt(language, name)

        # If no lesson status, ask for lesson status
        if not status.get("has_lesson_status"):
            language = get_user_language(self.memory_manager, user_id)
            name = self._get_user_name(user_id)
            self._store_memory(user_id, "onboarding_step_pending", "lesson_status", ttl_hours=2)
            return self._get_lesson_status_prompt(language, name)

        # Handle declined cases
        declined_response = self._handle_declined(status)
        if declined_response is not None:
            return declined_response

        # If onboarding complete, return None
        if status["onboarding_complete"]:
            return None

        # Handle explicit decline
        if self.onboarding.detect_decline_keywords(text) and "acim" in text.lower():
            self._store_memory(user_id, "acim_commitment", "declined", category="goals")
            return self._get_message("commitment_declined")

        # Return next onboarding prompt
        return self.onboarding.get_onboarding_prompt(user_id)
