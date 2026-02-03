import httpx
import logging
import json
import re
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from langdetect import detect, LangDetectException
from src.services.memory_manager import MemoryManager
from src.services.prompt_builder import PromptBuilder
from src.services.memory_extractor import MemoryExtractor
from src.services.onboarding_service import OnboardingService
from src.services.scheduler import SchedulerService
from src.services.dialogue import (
    call_ollama,
    detect_lesson_request,
    handle_lesson_request,
    format_lesson_message,
    translate_text,
    detect_one_time_reminder,
    get_pending_confirmation,
    resolve_pending_confirmation,
    handle_lesson_confirmation,
    get_user_language,
    detect_and_store_language,
    extract_and_store_memories,
    delete_user_and_data,
)
from src.config import settings
from src.models.database import Lesson, Schedule
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

class DialogueEngine:
    def __init__(self, db: Optional[Session] = None, memory_manager: Optional[MemoryManager] = None):
        self.db = db
        self.memory_manager = memory_manager or MemoryManager(db)
        self.prompt_builder = PromptBuilder(db, self.memory_manager) if db else None
        self.memory_extractor = MemoryExtractor()
        self.onboarding = OnboardingService(db) if db else None

    async def call_ollama(self, prompt: str, model: Optional[str] = None) -> str:
        """Delegate to dialogue.ollama_client."""
        return await call_ollama(prompt, model)

    async def process_message(
        self,
        user_id: int,
        text: str,
        session: Session,
        include_history: bool = True,
        history_turns: int = 4,
        include_lesson: bool = True,
    ) -> str:
        """
        Process user message with full context awareness.
        
        Automatically extracts and stores memories from the user message.
        Handles onboarding flow and schedule creation.
        
        Args:
            user_id: User ID from database
            text: User message
            session: SQLAlchemy session
            include_history: Include conversation history in context
            history_turns: Number of conversation turns to include
        
        Returns:
            AI response from Ollama
        """
        # Debug magic command: simulate next day for lesson progression
        if text.strip().lower() == "next_day":
            if self.memory_manager:
                self.memory_manager.store_memory(
                    user_id=user_id,
                    key="debug_day_offset",
                    value="1",
                    confidence=1.0,
                    source="debug_command",
                    ttl_hours=1,
                    category="conversation",
                )
            schedules = []
            if session:
                schedules = (
                    session.query(Schedule)
                    .filter(
                        Schedule.user_id == user_id,
                        Schedule.is_active == True,
                        Schedule.schedule_type == "daily",
                    )
                    .all()
                )
            if schedules:
                scheduler = SchedulerService.get_scheduler()
                now = datetime.now(timezone.utc)
                for schedule in schedules:
                    job_id = f"debug_next_day_{schedule.schedule_id}_{int(now.timestamp())}"
                    scheduler.add_job(
                        func=SchedulerService.execute_scheduled_task,
                        trigger=DateTrigger(run_date=now, timezone="UTC"),
                        args=[schedule.schedule_id],
                        id=job_id,
                        replace_existing=True,
                    )
                return "OK — simulating next day for 1 hour and triggering the scheduled morning message now."
            return "OK — simulating next day for 1 hour. No active daily schedule found."

        # FIRST: Extract memories from user message (this might store commitment, name, time, etc.)
        await extract_and_store_memories(
            self.memory_manager, self.memory_extractor, user_id, text
        )
        await detect_and_store_language(self.memory_manager, user_id, text)

        # Handle lesson confirmation replies (before onboarding/schedule logic)
        lesson_response = await handle_lesson_confirmation(
            user_id,
            text,
            session,
            self.memory_manager,
            self.onboarding,
            translate_text,
            lambda uid: get_user_language(self.memory_manager, uid),
            lambda les, lang: format_lesson_message(les, lang, self.call_ollama),
        )
        if lesson_response:
            return lesson_response

        # Handle one-time reminder requests
        reminder = detect_one_time_reminder(text)
        if reminder:
            schedule = SchedulerService.create_one_time_schedule(
                user_id=user_id,
                run_at=reminder["run_at"],
                message=reminder["message"],
                session=session,
            )
            confirmation = reminder["confirmation"]
            language = get_user_language(self.memory_manager, user_id)
            if language.lower() not in ["english", "en"]:
                confirmation = await translate_text(confirmation, language, self.call_ollama)
            return confirmation

        # If a schedule request is pending, continue schedule flow even without keywords
        if self.memory_manager:
            pending = self.memory_manager.get_memory(user_id, "schedule_request_pending")
            if pending and pending[0].get("value") == "true":
                schedule_response = await self._handle_schedule_request(user_id, text, session)
                if schedule_response:
                    return schedule_response
        
        # Check if user is requesting schedule/reminder setup (EXPLICIT REQUEST ONLY)
        if self.onboarding and self.onboarding.detect_schedule_request(text):
            if self.memory_manager:
                self.memory_manager.store_memory(
                    user_id=user_id,
                    key="schedule_request_pending",
                    value="true",
                    confidence=1.0,
                    source="dialogue_engine",
                    ttl_hours=1,
                    category="conversation",
                )
            schedule_response = await self._handle_schedule_request(user_id, text, session)
            if schedule_response:
                return schedule_response
        
        # Check if user is asking about a specific lesson (LESSON REQUEST - BEFORE ONBOARDING)
        lesson_request = detect_lesson_request(text)
        if lesson_request:
            lesson_response = await handle_lesson_request(
                lesson_request["lesson_id"], text, session
            )
            if lesson_response:
                return lesson_response
        
        # Check if user needs onboarding (new users)
        if self.onboarding and self.onboarding.should_show_onboarding(user_id):
            onboarding_response = await self._handle_onboarding(user_id, text, session)
            if onboarding_response:
                return onboarding_response

        # Auto-send next lesson on a new day when user makes contact
        if include_lesson and self.prompt_builder:
            auto_message = await self._maybe_send_next_lesson(user_id, text, session)
            if auto_message:
                return auto_message
        
        # Regular conversation
        if not self.prompt_builder:
            # Fallback for cases without DB session
            prompt = f"{settings.SYSTEM_PROMPT}\nUser: {text}\n\nAssistant:"
        else:
            # Build context-aware prompt
            prompt = self.prompt_builder.build_prompt(
                user_id=user_id,
                user_input=text,
                system_prompt=settings.SYSTEM_PROMPT,
                include_lesson=include_lesson,
                include_conversation_history=include_history,
                history_turns=history_turns,
            )
        
        # Call Ollama
        response = await self.call_ollama(prompt)
        
        return response

    async def _maybe_send_next_lesson(self, user_id: int, text: str, session: Session) -> Optional[str]:
        context = self.prompt_builder.get_today_lesson_context(user_id)
        lesson_text = context.get("lesson_text", "")
        state = context.get("state", {})
        if not lesson_text or not state.get("advanced_by_day"):
            return None

        if not self._is_simple_greeting(text):
            return None

        lesson_id = state.get("lesson_id")
        previous_lesson_id = state.get("previous_lesson_id")
        if not lesson_id:
            return None

        lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
        if not lesson:
            return None

        language = get_user_language(self.memory_manager, user_id)
        message = await format_lesson_message(lesson, language, self.call_ollama)

        repeat_note = None
        if previous_lesson_id:
            repeat_note = (
                f"If you'd like to repeat Lesson {previous_lesson_id} instead, just let me know."
            )
            if language.lower() not in ["english", "en"]:
                repeat_note = await translate_text(repeat_note, language, self.call_ollama)

        if repeat_note:
            message = f"{message}\n\n{repeat_note}"

        # Track last sent lesson for future day-advance logic
        self.memory_manager.store_memory(
            user_id=user_id,
            key="last_sent_lesson_id",
            value=str(lesson.lesson_id),
            category="progress",
            confidence=1.0,
            source="dialogue_engine_auto_lesson",
        )

        return message

    def _is_simple_greeting(self, text: str) -> bool:
        cleaned = re.sub(r"[^a-zA-Z\s]", "", text or "").strip().lower()
        if not cleaned:
            return True
        if len(cleaned.split()) <= 3:
            greetings = {
                "hi", "hello", "hey", "good morning", "good evening",
                "good afternoon", "morning", "evening", "afternoon",
                "hei", "hallo", "god morgen", "god kveld", "god ettermiddag",
            }
            return cleaned in greetings
        return False

    def _get_user_language(self, user_id: int) -> str:
        """
        Get user's preferred language from memories table.
        
        Looks for memory with key='user_language' and category='preference'.
        Returns the language value (e.g., 'Norwegian', 'English') or 'English' as default.
        
        Args:
            user_id: The user's ID
            
        Returns:
            Language string (e.g., 'Norwegian', 'English')
        """
        memories = self.memory_manager.get_memory(user_id, "user_language")
        if memories and len(memories) > 0:
            # get_memory returns a list, get the first/most recent one
            return memories[0].value
        return "English"  # Default to English if not found


    async def _handle_onboarding(self, user_id: int, text: str, session: Session) -> Optional[str]:
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
                    elif consent is False:
                        # User declined consent during onboarding - delete the user
                        self._delete_user(user_id)
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
                            language = self._get_user_language(user_id)
                            welcome_msg = self.onboarding.get_lesson_1_welcome_message(user_id)
                            lesson_msg = await self._format_lesson_message(lesson, language)
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
                            language = self._get_user_language(user_id)
                            continuation_msg = self.onboarding.get_continuation_welcome_message(user_id, lesson_id)
                            lesson_msg = await self._format_lesson_message(lesson, language)
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
                        language = self._get_user_language(user_id)
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

                    language = self._get_user_language(user_id)
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

    async def _handle_schedule_request(self, user_id: int, text: str, session: Session) -> Optional[str]:
        """
        Handle explicit schedule/reminder requests.
        
        Returns:
            Schedule setup response or None
        """
        # Check if user already has commitment
        status = self.onboarding.get_onboarding_status(user_id)
        
        if not status["has_commitment"]:
            # Need commitment first
            return self.onboarding.get_onboarding_prompt(user_id)
        
        # Check if they already have a schedule
        schedules = SchedulerService.get_user_schedules(user_id)
        if schedules:
            schedule = schedules[0]
            hour, minute = schedule.next_send_time.hour, schedule.next_send_time.minute
            if self.memory_manager:
                self.memory_manager.store_memory(
                    user_id=user_id,
                    key="schedule_request_pending",
                    value="false",
                    confidence=1.0,
                    source="dialogue_engine",
                    ttl_hours=1,
                    category="conversation",
                )
            return f"""You're already all set up! ✨

You have a daily reminder for {hour:02d}:{minute:02d} UTC.

Would you like to:
• Change the time?
• Add another reminder?
• Cancel the current reminder?"""

        # Check if they have a preferred time stored
        time_memories = self.memory_manager.get_memory(user_id, "preferred_lesson_time")

        if not time_memories:
            # Ask for their preferred time
            if self.memory_manager:
                self.memory_manager.store_memory(
                    user_id=user_id,
                    key="schedule_request_pending",
                    value="true",
                    confidence=1.0,
                    source="dialogue_engine",
                    ttl_hours=1,
                    category="conversation",
                )
            return """Great! I'll set up daily reminders for your ACIM lessons.

When would you like to receive them? (e.g., "9:00 AM", "morning", "evening", "8:30 PM")"""

        # They have a time preference - create the schedule
        time_str = time_memories[0]["value"]

        try:
            schedule = SchedulerService.create_daily_schedule(
                user_id=user_id,
                lesson_id=None,
                time_str=time_str,
                session=session,
            )

            hour, minute = SchedulerService.parse_time_string(time_str)

            name_memories = self.memory_manager.get_memory(user_id, "first_name")
            name = name_memories[0]["value"] if name_memories else "friend"

            if self.memory_manager:
                self.memory_manager.store_memory(
                    user_id=user_id,
                    key="schedule_request_pending",
                    value="false",
                    confidence=1.0,
                    source="dialogue_engine",
                    ttl_hours=1,
                    category="conversation",
                )

            return f"""Perfect, {name}! ✨

I've scheduled your daily ACIM lesson for {hour:02d}:{minute:02d} UTC each day.

Each day at this time, I'll send you one lesson. Remember: consistency is key. Even if you can only spend 5 minutes with the lesson, that daily practice will transform your perception.

Your first lesson will arrive tomorrow at {hour:02d}:{minute:02d} UTC. 🙏"""

        except Exception as e:
            logger.error(f"Error creating schedule: {e}")
            return "I had trouble setting up your schedule. Could you tell me your preferred time? (e.g., '9:00 AM' or 'morning')"

    def get_conversation_state(self, user_id: int, session: Session) -> Dict[str, Any]:
        """
        Return current user memory and profile for conversation context.
        """
        if not self.memory_manager or not self.prompt_builder:
            return {}
        
        return {
            "user_id": user_id,
            "profile": {
                "goals": self.memory_manager.get_memory(user_id, "learning_goal"),
                "preferences": self.memory_manager.get_memory(user_id, "preferred_tone"),
            },
            "recent_history": self.prompt_builder._build_conversation_history(user_id, num_turns=3),
        }

    def set_conversation_state(self, user_id: int, state: Dict[str, Any], session: Session):
        """
        Update conversation context for multi-turn dialogue.
        Stores key insights and state in memory system.
        """
        if not self.memory_manager:
            return
        
        # Store state snapshots in memory if needed
        # Example: persist current lesson or topic
        if "current_topic" in state:
            self.memory_manager.store_memory(
                user_id=user_id,
                key="conversation_state",
                value=state["current_topic"],
                source="dialogue_engine",
                ttl_hours=24,  # 24-hour window for active conversation
                category="conversation",
            )

    def get_onboarding_prompt(self) -> str:
        """
        Return onboarding prompt sequence for new users.
        """
        if not self.prompt_builder:
            return "Welcome! What's your name?"
        
        return self.prompt_builder.build_onboarding_prompt(settings.SYSTEM_PROMPT)
