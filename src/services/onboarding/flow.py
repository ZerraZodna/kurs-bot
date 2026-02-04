from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.models.database import Lesson
from src.services.gdpr_service import record_consent
from src.services.dialogue.lesson_handler import format_lesson_message
from src.services.dialogue.memory_helpers import delete_user_and_data, get_user_language

logger = logging.getLogger(__name__)


class OnboardingFlow:
    def __init__(self, memory_manager, onboarding_service, call_ollama):
        self.memory_manager = memory_manager
        self.onboarding = onboarding_service
        self.call_ollama = call_ollama

    async def handle_onboarding(self, user_id: int, text: str, session: Session) -> Optional[str]:
        """
        Handle onboarding flow.

        Onboarding just collects basic info (name, commitment).
        It does NOT create schedules - that only happens on explicit user request.

        Returns:
            Onboarding response or None if not in onboarding flow
        """
        status = self.onboarding.get_onboarding_status(user_id)

        # Handle pending onboarding step explicitly
        if self.memory_manager:
            pending_step = self.memory_manager.get_memory(user_id, "onboarding_step_pending")
            if pending_step:
                step = str(pending_step[0].get("value", "")).lower()
                if step == "consent":
                    consent = self.onboarding.detect_consent_keywords(text)
                    if consent is True:
                        self.memory_manager.store_memory(
                            user_id=user_id,
                            key="data_consent",
                            value="granted",
                            confidence=1.0,
                            source="dialogue_engine_consent",
                            category="profile",
                        )
                        record_consent(
                            session,
                            user_id=user_id,
                            scope="data_storage",
                            granted=True,
                            source="dialogue_engine_consent",
                        )
                    elif consent is False:
                        record_consent(
                            session,
                            user_id=user_id,
                            scope="data_storage",
                            granted=False,
                            source="dialogue_engine_consent",
                        )
                        # User declined consent during onboarding - delete the user
                        delete_user_and_data(session, user_id)
                        return "Understood. I won't store your information. If you change your mind, just message me again."
                elif step == "commitment":
                    if self.onboarding.detect_decline_keywords(text):
                        self.memory_manager.store_memory(
                            user_id=user_id,
                            key="acim_commitment",
                            value="declined",
                            confidence=1.0,
                            source="dialogue_engine_commitment",
                            category="goals",
                        )
                        return "Understood. I won't ask about ACIM lessons. If you want to resume later, just message me."
                    if self.onboarding.detect_commitment_keywords(text):
                        self.memory_manager.store_memory(
                            user_id=user_id,
                            key="acim_commitment",
                            value="committed to ACIM lessons",
                            confidence=1.0,
                            source="dialogue_engine_commitment",
                            category="goals",
                        )
                        return self.onboarding.get_onboarding_prompt(user_id)
                elif step == "lesson_status":
                    response = self.onboarding.handle_lesson_status_response(user_id, text)

                    if response.get("action") == "send_lesson_1":
                        self.memory_manager.store_memory(
                            user_id=user_id,
                            key="current_lesson",
                            value="1",
                            category="progress",
                            confidence=1.0,
                            source="onboarding_lesson_status",
                        )

                        completion_msg = None
                        completion_sent = self.memory_manager.get_memory(user_id, "onboarding_complete_message_sent")
                        if not completion_sent:
                            status = self.onboarding.get_onboarding_status(user_id)
                            if status.get("has_name") and status.get("has_consent") and status.get("has_commitment"):
                                completion_msg = self.onboarding.get_onboarding_complete_message(user_id)
                                self.memory_manager.store_memory(
                                    user_id=user_id,
                                    key="onboarding_complete_message_sent",
                                    value="true",
                                    category="conversation",
                                    ttl_hours=365 * 24,
                                    source="dialogue_engine",
                                    allow_duplicates=False,
                                )
                                self.memory_manager.store_memory(
                                    user_id=user_id,
                                    key="pending_lesson_delivery",
                                    value="1",
                                    category="conversation",
                                    ttl_hours=1,
                                    source="dialogue_engine",
                                    allow_duplicates=False,
                                )
                                self.memory_manager.store_memory(
                                    user_id=user_id,
                                    key="onboarding_step_pending",
                                    value="resolved",
                                    category="conversation",
                                    ttl_hours=0.1,
                                    source="dialogue_engine",
                                    allow_duplicates=False,
                                )
                                return completion_msg

                        lesson = session.query(Lesson).filter(Lesson.lesson_id == 1).first()
                        if lesson:
                            language = get_user_language(self.memory_manager, user_id)
                            welcome_msg = self.onboarding.get_lesson_1_welcome_message(user_id)
                            lesson_msg = await format_lesson_message(lesson, language, self.call_ollama)
                            self.memory_manager.store_memory(
                                user_id=user_id,
                                key="pending_lesson_delivery",
                                value="",
                                category="conversation",
                                ttl_hours=0.1,
                                source="dialogue_engine",
                                allow_duplicates=False,
                            )
                            self.memory_manager.store_memory(
                                user_id=user_id,
                                key="onboarding_step_pending",
                                value="resolved",
                                category="conversation",
                                ttl_hours=0.1,
                                source="dialogue_engine",
                                allow_duplicates=False,
                            )
                            return f"{welcome_msg}\n\n{lesson_msg}"

                        return "I couldn't load Lesson 1 right now. Please try again."

                    if response.get("action") == "send_specific_lesson":
                        lesson_id = response["lesson_id"]
                        self.memory_manager.store_memory(
                            user_id=user_id,
                            key="current_lesson",
                            value=str(lesson_id),
                            category="progress",
                            confidence=1.0,
                            source="onboarding_lesson_status",
                        )

                        completion_msg = None
                        completion_sent = self.memory_manager.get_memory(user_id, "onboarding_complete_message_sent")
                        if not completion_sent:
                            status = self.onboarding.get_onboarding_status(user_id)
                            if status.get("has_name") and status.get("has_consent") and status.get("has_commitment"):
                                completion_msg = self.onboarding.get_onboarding_complete_message(user_id)
                                self.memory_manager.store_memory(
                                    user_id=user_id,
                                    key="onboarding_complete_message_sent",
                                    value="true",
                                    category="conversation",
                                    ttl_hours=365 * 24,
                                    source="dialogue_engine",
                                    allow_duplicates=False,
                                )
                                self.memory_manager.store_memory(
                                    user_id=user_id,
                                    key="pending_lesson_delivery",
                                    value=str(lesson_id),
                                    category="conversation",
                                    ttl_hours=1,
                                    source="dialogue_engine",
                                    allow_duplicates=False,
                                )
                                self.memory_manager.store_memory(
                                    user_id=user_id,
                                    key="onboarding_step_pending",
                                    value="resolved",
                                    category="conversation",
                                    ttl_hours=0.1,
                                    source="dialogue_engine",
                                    allow_duplicates=False,
                                )
                                return completion_msg

                        lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
                        if lesson:
                            language = get_user_language(self.memory_manager, user_id)
                            continuation_msg = self.onboarding.get_continuation_welcome_message(user_id, lesson_id)
                            lesson_msg = await format_lesson_message(lesson, language, self.call_ollama)
                            self.memory_manager.store_memory(
                                user_id=user_id,
                                key="pending_lesson_delivery",
                                value="",
                                category="conversation",
                                ttl_hours=0.1,
                                source="dialogue_engine",
                                allow_duplicates=False,
                            )
                            self.memory_manager.store_memory(
                                user_id=user_id,
                                key="onboarding_step_pending",
                                value="resolved",
                                category="conversation",
                                ttl_hours=0.1,
                                source="dialogue_engine",
                                allow_duplicates=False,
                            )
                            return f"{continuation_msg}\n\n{lesson_msg}"

                        return "I couldn't load that lesson right now. Please try again."

                    if response.get("action") == "ask_lesson_number":
                        language = get_user_language(self.memory_manager, user_id)
                        message = "Great! Which lesson are you currently working on?"
                        if language == "Norwegian":
                            message = "Flott! Hvilken leksjon jobber du med nå?"
                        self.memory_manager.store_memory(
                            user_id=user_id,
                            key="onboarding_step_pending",
                            value="lesson_status",
                            category="conversation",
                            ttl_hours=2,
                            source="dialogue_engine",
                            allow_duplicates=False,
                        )
                        return message

                    language = get_user_language(self.memory_manager, user_id)
                    message = "Are you completely new to ACIM, or have you already started? (Answer 'new' or 'continuing')"
                    if language == "Norwegian":
                        message = "Er du helt ny til ACIM, eller har du allerede begynt? (Svar 'ny' eller 'fortsetter')"
                    self.memory_manager.store_memory(
                        user_id=user_id,
                        key="onboarding_step_pending",
                        value="lesson_status",
                        category="conversation",
                        ttl_hours=2,
                        source="dialogue_engine",
                        allow_duplicates=False,
                    )
                    return message

                # Clear pending step
                self.memory_manager.store_memory(
                    user_id=user_id,
                    key="onboarding_step_pending",
                    value="resolved",
                    category="conversation",
                    ttl_hours=0.1,
                    source="dialogue_engine",
                    allow_duplicates=False,
                )

        # Exit if user declined consent or commitment
        if status.get("declined_consent"):
            # User already declined and should have been deleted - don't process further
            return None
        if status.get("declined_commitment"):
            return "Understood. I won't ask about ACIM lessons. If you want to resume later, just message me."

        # If onboarding just completed, show welcome message
        if status["onboarding_complete"]:
            return None

        # If user explicitly declines ACIM, honor it immediately
        if self.onboarding.detect_decline_keywords(text) and "acim" in text.lower():
            self.memory_manager.store_memory(
                user_id=user_id,
                key="acim_commitment",
                value="declined",
                confidence=1.0,
                source="dialogue_engine_commitment",
                category="goals",
            )
            return "Understood. I won't ask about ACIM lessons. If you want to resume later, just message me."

        # Handle consent step
        if status.get("has_name") and not status.get("has_consent"):
            consent = self.onboarding.detect_consent_keywords(text)
            if consent is True:
                self.memory_manager.store_memory(
                    user_id=user_id,
                    key="data_consent",
                    value="granted",
                    confidence=1.0,
                    source="dialogue_engine_consent",
                    category="profile",
                )
                record_consent(
                    session,
                    user_id=user_id,
                    scope="data_storage",
                    granted=True,
                    source="dialogue_engine_consent",
                )
                return self.onboarding.get_onboarding_prompt(user_id)
            if consent is False:
                self.memory_manager.store_memory(
                    user_id=user_id,
                    key="data_consent",
                    value="declined",
                    confidence=1.0,
                    source="dialogue_engine_consent",
                    category="profile",
                )
                record_consent(
                    session,
                    user_id=user_id,
                    scope="data_storage",
                    granted=False,
                    source="dialogue_engine_consent",
                )
                return "Understood. I won't store your information. If you change your mind, just message me again."

        # If they're answering commitment question, check for affirmative/decline
        if status["has_name"] and status.get("has_consent") and not status["has_commitment"]:
            if self.onboarding.detect_decline_keywords(text):
                self.memory_manager.store_memory(
                    user_id=user_id,
                    key="acim_commitment",
                    value="declined",
                    confidence=1.0,
                    source="dialogue_engine_commitment",
                    category="goals",
                )
                return "Understood. I won't ask about ACIM lessons. If you want to resume later, just message me."
            if self.onboarding.detect_commitment_keywords(text):
                # Ensure commitment memory exists even if extractor missed it
                commit_memories = self.memory_manager.get_memory(user_id, "acim_commitment")
                if not commit_memories:
                    self.memory_manager.store_memory(
                        user_id=user_id,
                        key="acim_commitment",
                        value="committed to ACIM lessons",
                        confidence=1.0,
                        source="dialogue_engine_commitment",
                        category="goals",
                    )
                logger.info(f"User {user_id} expressed interest in ACIM lessons")
                # Move to lesson status step
                return self.onboarding.get_onboarding_prompt(user_id)

        # Return next onboarding prompt
        return self.onboarding.get_onboarding_prompt(user_id)
