from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session
from src.models.database import User

from src.models.database import Lesson
from src.services.gdpr_service import record_consent
from src.services.dialogue.lesson_handler import format_lesson_message
from src.services.dialogue.memory_helpers import delete_user_and_data, get_user_language
from src.onboarding import prompts as prompts_module
from src.scheduler.lesson_state import set_current_lesson

logger = logging.getLogger(__name__)


class OnboardingStep(Enum):
    CONSENT = "consent"
    COMMITMENT = "commitment"
    LESSON_STATUS = "lesson_status"
    NAME = "name"



class OnboardingFlow:
    def __init__(self, memory_manager, onboarding_service, call_ollama):
        self.memory_manager = memory_manager
        self.onboarding = onboarding_service
        self.call_ollama = call_ollama

    def _get_pending_step(self, user_id: int) -> Optional[str]:
        pending_step = self.memory_manager.get_memory(user_id, "onboarding_step_pending")
        # Debug trace
        print(f"[ONBOARD DEBUG] _get_pending_step - user_id={user_id} -> {pending_step}")
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
        print(f"[ONBOARD DEBUG] _resolve_pending_step - user_id={user_id}")

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
        print(f"[ONBOARD DEBUG] _store_memory - user_id={user_id} key={key} value={value} category={category} ttl={ttl_hours}")

    def _get_message(self, key: str, language: str = "en") -> str:
        # Delegate prompt retrieval to prompts.py (centralized prompts)
        # The helper normalizes language codes; callers can format the returned
        # template (e.g. fill `{name}`) when needed.
        return prompts_module.get_onboarding_message(key, language)

    def _get_user_name(self, user_id: int) -> str:
        name_memories = self.memory_manager.get_memory(user_id, "first_name")
        if not name_memories:
            name_memories = self.memory_manager.get_memory(user_id, "name")
        name = name_memories[0]["value"] if name_memories else "friend"
        print(f"[ONBOARD DEBUG] _get_user_name - user_id={user_id} -> {name}")
        return name

    def _get_commitment_prompt(self, language: str, name: str) -> str:
        prompt = self._get_message("commitment_prompt", language)
        return prompt.format(name=name)

    def _get_lesson_status_prompt(self, language: str, name: str) -> str:
        prompt = self._get_message("ask_new_or_continuing", language)
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
        elif step == "name":
            return await self._handle_name_pending(user_id, text, session)
        return None

    async def _handle_name_pending(self, user_id: int, text: str, session: Session) -> Optional[str]:
        """Handle the pending 'name' step.

        Expected behaviour:
        - If user confirms (yes), store the Telegram first_name from DB as `first_name` memory.
        - If user replies with a name, store that as `first_name` memory.
        - If user explicitly declines, ask what they prefer to be called.
        After storing the preferred name, continue onboarding (next prompt from service).
        """
        print(f"[ONBOARD DEBUG] _handle_name_pending - user_id={user_id} text={text}")
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
                    self._store_memory(user_id, "first_name", db_user.first_name, category="profile")
                    self._resolve_pending_step(user_id)
                    return self.onboarding.get_onboarding_prompt(user_id)
            except Exception:
                pass
            # fallback: ask for name explicitly
            self._store_memory(user_id, "onboarding_step_pending", OnboardingStep.NAME.value, ttl_hours=2)
            language = get_user_language(self.memory_manager, user_id)
            if language == "no":
                return "Hva vil du at jeg skal kalle deg?"
            return "What would you like me to call you?"

        if lname in negatives:
            # user declined — ask for preferred name explicitly
            self._store_memory(user_id, "onboarding_step_pending", OnboardingStep.NAME.value, ttl_hours=2)
            language = get_user_language(self.memory_manager, user_id)
            if language == "no":
                return "Hva vil du at jeg skal kalle deg?"
            return "What would you like me to call you?"

        # Otherwise, treat the reply as the preferred name and store it
        preferred = t
        if preferred:
            self._store_memory(user_id, "first_name", preferred, category="profile")
            self._resolve_pending_step(user_id)
            return self.onboarding.get_onboarding_prompt(user_id)

        return None

    def _handle_consent_pending(self, user_id: int, text: str, session: Session) -> Optional[str]:
        print(f"[ONBOARD DEBUG] _handle_consent_pending - user_id={user_id} text={text}")
        consent = self.onboarding.detect_consent_keywords(text)
        if consent is True:
            self._store_memory(user_id, "data_consent", "granted", category="profile")
            record_consent(session, user_id, "data_storage", True, "dialogue_engine_consent")
            self._resolve_pending_step(user_id)
            # Return a localized thank-you and continue onboarding flow
            language = get_user_language(self.memory_manager, user_id)
            print(f"[ONBOARD DEBUG] consent granted - user_id={user_id} language={language}")
            thank_you = self._get_message("consent_granted", language)
            next_prompt = self.onboarding.get_onboarding_prompt(user_id)
            if next_prompt:
                # Insert the thank-you after the initial greeting line of the
                # next prompt (e.g., "Beautiful, {name}!") so the flow reads:
                # "Beautiful, {name}!\nThank you...\nAre you interested..."
                parts = next_prompt.split("\n", 1)
                if len(parts) == 2:
                    head, tail = parts[0], parts[1]
                    return f"{head}\n{thank_you}\n{tail}"
                # Fallback: append thank-you if no newline present
                return f"{next_prompt}\n\n{thank_you}"
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
        # If the user replied with just a number (e.g., "7"), treat that as
        # an explicit lesson number and persist it immediately to avoid the
        # LLM picking up lesson context and returning lesson content.
        t = (text or "").strip()
        import re as _re
        m = _re.match(r"^(\d{1,3})$", t)
        if m:
            try:
                lesson_id = int(m.group(1))
                if 1 <= lesson_id <= 365:
                    # Persist lesson (onboarding context) but DO NOT deliver the
                    # lesson now. Instead, mark onboarding progressed, create
                    # the default schedule, and return the onboarding-complete
                    # message so the user receives the welcome + summary.
                    set_current_lesson(self.memory_manager, user_id, str(lesson_id))
                    self._resolve_pending_step(user_id)
                    self._set_pending_lesson_delivery(user_id)
                    try:
                        # OnboardingService.get_onboarding_complete_message will
                        # auto-create the default schedule and return the text.
                        return self.onboarding.get_onboarding_complete_message(user_id)
                    except Exception:
                        # Fallback: continue onboarding prompt if creation fails
                        return self.onboarding.get_onboarding_prompt(user_id)
            except Exception:
                pass

        response = self.onboarding.handle_lesson_status_response(user_id, text)
        action = response.get("action")

        # If user explicitly asks to start with Lesson 1, deliver it now
        if action == "send_lesson_1":
            return await self._deliver_lesson(user_id, 1, session, is_first=True)

        # If user indicates a specific lesson number, persist the lesson
        # but do NOT automatically deliver the lesson during onboarding.
        # Instead, advance onboarding to the next logical prompt (schedule).
        elif action == "send_specific_lesson":
            lesson_id = response.get("lesson_id")
            # `handle_lesson_status_response` already stored `current_lesson`.
            # If onboarding is now complete (name, consent, commitment), ask
            # for preferred lesson time so we can set up daily reminders.
            status = self.onboarding.get_onboarding_status(user_id)
            if status.get("onboarding_complete") or (
                status.get("has_name") and status.get("has_consent") and status.get("has_commitment")
            ):
                # Onboarding satisfied: persist lesson, create default
                # schedule and return the onboarding completion message
                try:
                    return self.onboarding.get_onboarding_complete_message(user_id)
                except Exception:
                    return self.onboarding.get_onboarding_prompt(user_id)
            # Otherwise, continue onboarding flow normally
            return self.onboarding.get_onboarding_prompt(user_id)

        elif action == "ask_lesson_number":
            language = get_user_language(self.memory_manager, user_id)
            self._store_memory(user_id, "onboarding_step_pending", OnboardingStep.LESSON_STATUS.value, ttl_hours=2)
            return self._get_message("ask_lesson_number", language)

        language = get_user_language(self.memory_manager, user_id)
        self._store_memory(user_id, "onboarding_step_pending", OnboardingStep.LESSON_STATUS.value, ttl_hours=2)
        return self._get_message("ask_new_or_continuing", language).format(name=self._get_user_name(user_id))

    async def _deliver_lesson(self, user_id: int, lesson_id: int, session: Session, is_first: bool) -> str:
        # Record user progress using consolidated lesson_state helper
        set_current_lesson(self.memory_manager, user_id, str(lesson_id))

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
        print(f"[ONBOARD DEBUG] handle_onboarding - user_id={user_id} text={text} status={status}")

        # If there is a pending onboarding step, handle it first so replies
        # to prompts (e.g. consent "yes") are processed instead of re-asking.
        pending_step = self._get_pending_step(user_id)
        if pending_step:
            print(f"[ONBOARD DEBUG] pending_step detected: {pending_step} for user {user_id}")
            response = await self._handle_pending_step(user_id, text, session, pending_step)
            if response:
                return response
            self._resolve_pending_step(user_id)

        # If no name info exists, delegate to the onboarding service which
        # may prefer to ask permission to use an existing Telegram `first_name`.
        if not status.get("has_name"):
            print(f"[ONBOARD DEBUG] asking for name (no name) delegating to service user_id={user_id}")
            return self.onboarding.get_onboarding_prompt(user_id)

        # If no consent, ask for consent
        if not status.get("has_consent"):
            language = get_user_language(self.memory_manager, user_id)
            self._store_memory(user_id, "onboarding_step_pending", "consent", ttl_hours=2)
            print(f"[ONBOARD DEBUG] asking for consent (no consent) user_id={user_id} language={language}")
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
