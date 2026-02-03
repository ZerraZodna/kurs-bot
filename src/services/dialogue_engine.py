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
from src.config import settings
from src.models.database import Lesson
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"  # Default Ollama endpoint

class DialogueEngine:
    def __init__(self, db: Optional[Session] = None, memory_manager: Optional[MemoryManager] = None):
        self.db = db
        self.memory_manager = memory_manager or MemoryManager(db)
        self.prompt_builder = PromptBuilder(db, self.memory_manager) if db else None
        self.memory_extractor = MemoryExtractor()
        self.onboarding = OnboardingService(db) if db else None

    async def call_ollama(self, prompt: str, model: Optional[str] = None) -> str:
        model = model or settings.OLLAMA_MODEL
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(OLLAMA_URL, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "[No response from Ollama]")
        except Exception as e:
            logger.error(f"[Ollama error] {e}")
            return "[Sorry, I couldn't process your request right now.]"

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
            return "OK — simulating next day for 1 hour. Send any message to get the next lesson."

        # FIRST: Extract memories from user message (this might store commitment, name, time, etc.)
        await self._extract_and_store_memories(user_id, text, session)

        # Handle lesson confirmation replies (before onboarding/schedule logic)
        lesson_response = await self._handle_lesson_confirmation(user_id, text, session)
        if lesson_response:
            return lesson_response

        # Handle one-time reminder requests
        reminder = self._parse_one_time_reminder(text)
        if reminder:
            schedule = SchedulerService.create_one_time_schedule(
                user_id=user_id,
                run_at=reminder["run_at"],
                message=reminder["message"],
                session=session,
            )
            confirmation = reminder["confirmation"]
            language = self._get_user_language(user_id)
            if language.lower() not in ["english", "en"]:
                confirmation = await self._translate_text(confirmation, language)
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
        lesson_request = self._detect_lesson_request(text)
        if lesson_request:
            lesson_response = await self._handle_lesson_request(lesson_request["lesson_id"], text, session)
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

        language = self._get_user_language(user_id)
        message = await self._format_lesson_message(lesson, language)

        repeat_note = None
        if previous_lesson_id:
            repeat_note = (
                f"If you'd like to repeat Lesson {previous_lesson_id} instead, just let me know."
            )
            if language.lower() not in ["english", "en"]:
                repeat_note = await self._translate_text(repeat_note, language)

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

    def _parse_one_time_reminder(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse one-time reminders like 'remind me to X in 5 minutes'."""
        msg = text.strip()
        lower = msg.lower()

        trigger_phrases = ["remind me", "påminn meg", "minn meg"]
        if not any(tp in lower for tp in trigger_phrases):
            return None

        # Pattern: remind me to <message> in 5 minutes
        pattern_1 = re.compile(
            r"(?:remind me|påminn meg|minn meg)\s+(?:to\s+)?(?P<message>.+?)\s+(?:in|om)\s+(?P<amount>\d+)\s*(?P<unit>minutes?|hours?|minutter|timer)",
            re.IGNORECASE,
        )

        # Pattern: remind me in 5 minutes to <message>
        pattern_2 = re.compile(
            r"(?:remind me|påminn meg|minn meg)\s+(?:in|om)\s+(?P<amount>\d+)\s*(?P<unit>minutes?|hours?|minutter|timer)\s*(?:to\s+)?(?P<message>.+)",
            re.IGNORECASE,
        )

        match = pattern_1.search(msg) or pattern_2.search(msg)
        if match:
            message = match.group("message").strip().strip('"').strip("'")
            amount = int(match.group("amount"))
            unit = match.group("unit").lower()

            if amount <= 0 or not message:
                return None

            minutes = amount
            if unit in ["hour", "hours", "timer"]:
                minutes = amount * 60

            run_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
            confirmation = f"Got it! I'll remind you in {amount} {unit}."

            return {"message": message, "run_at": run_at, "confirmation": confirmation}

        # Pattern: remind me at HH:MM to <message> (today/tomorrow)
        pattern_at = re.compile(
            r"(?:remind me|påminn meg|minn meg)\s+(?:at|kl)\s+(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?:to\s+)?(?P<message>.+)",
            re.IGNORECASE,
        )

        match = pattern_at.search(msg)
        if match:
            hour = int(match.group("hour"))
            minute = int(match.group("minute") or 0)
            message = match.group("message").strip().strip('"').strip("'")

            if not message:
                return None

            now = datetime.now(timezone.utc)
            run_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if run_at <= now:
                run_at += timedelta(days=1)
            confirmation = f"Got it! I'll remind you at {hour:02d}:{minute:02d} UTC."

            return {"message": message, "run_at": run_at, "confirmation": confirmation}

        return None

    async def _handle_lesson_confirmation(self, user_id: int, text: str, session: Session) -> Optional[str]:
        """Handle replies to daily lesson completion prompts."""
        if not self.memory_manager:
            return None

        pending = self._get_pending_confirmation(user_id)
        if not pending:
            return None

        message_lower = text.lower().strip()

        # Detect yes/no responses
        is_yes = self.onboarding.detect_commitment_keywords(message_lower) if self.onboarding else False
        no_keywords = [
            "no", "not yet", "nope", "nei", "ikke ennå", "ikke enda",
            "ikke", "ikke ferdig", "senere",
        ]
        is_no = any(k in message_lower for k in no_keywords)

        if not is_yes and not is_no:
            return None

        lesson_id = pending.get("lesson_id")
        next_id = pending.get("next_lesson_id")

        if is_no:
            self._resolve_pending_confirmation(user_id)
            message = "No problem. Take your time and reply 'yes' when you're ready to continue."
            language = self._get_user_language(user_id)
            if language.lower() not in ["english", "en"]:
                message = await self._translate_text(message, language)
            return message

        # Yes: mark completed and send next lesson
        if lesson_id:
            self.memory_manager.store_memory(
                user_id=user_id,
                key="lesson_completed",
                value=str(lesson_id),
                category="progress",
                confidence=1.0,
                source="dialogue_engine_lesson_confirmation",
            )

        lesson = session.query(Lesson).filter(Lesson.lesson_id == next_id).first() if next_id else None
        if not lesson:
            self._resolve_pending_confirmation(user_id)
            return "Thanks! I couldn't find the next lesson right now."

        language = self._get_user_language(user_id)
        message = await self._format_lesson_message(lesson, language)

        # Update last sent lesson id
        self.memory_manager.store_memory(
            user_id=user_id,
            key="last_sent_lesson_id",
            value=str(lesson.lesson_id),
            category="progress",
            confidence=1.0,
            source="dialogue_engine_lesson_confirmation",
        )

        self._resolve_pending_confirmation(user_id)
        return message

    def _get_pending_confirmation(self, user_id: int) -> Optional[dict]:
        memories = self.memory_manager.get_memory(user_id, "lesson_confirmation_pending")
        if not memories:
            return None
        def _normalize_dt(value: Optional[datetime]) -> datetime:
            if isinstance(value, datetime):
                return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
            return datetime.min.replace(tzinfo=timezone.utc)

        latest = max(memories, key=lambda m: _normalize_dt(m.get("created_at")))
        raw = latest.get("value", "")
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("lesson_id"):
                return data
        except Exception:
            return None
        return None

    def _resolve_pending_confirmation(self, user_id: int) -> None:
        # Archive pending by replacing with a short-lived resolved marker
        self.memory_manager.store_memory(
            user_id=user_id,
            key="lesson_confirmation_pending",
            value=json.dumps({"resolved": True, "timestamp": datetime.now(timezone.utc).isoformat()}),
            category="conversation",
            ttl_hours=12,
            source="dialogue_engine",
        )

    def _get_user_language(self, user_id: int) -> str:
        memories = self.memory_manager.get_memory(user_id, "user_language")
        return memories[0].get("value", "English") if memories else "English"

    async def _format_lesson_message(self, lesson: Lesson, language: str) -> str:
        text = f"Lesson {lesson.lesson_id}: {lesson.title}\n\n{lesson.content}"
        if language.lower() in ["english", "en"]:
            return text
        return await self._translate_text(text, language)

    async def _translate_text(self, text: str, language: str) -> str:
        try:
            prompt = (
                f"Translate the following text to {language}. "
                "Preserve paragraph breaks and meaning. Return only the translation.\n\n"
                f"{text}"
            )
            payload = {
                "model": settings.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(settings.OLLAMA_URL, json=payload, timeout=60.0)
                response.raise_for_status()
                data = response.json()
                return data.get("response", text) or text
        except Exception as e:
            logger.warning(f"Translation failed, sending original text: {e}")
            return text

    async def _extract_and_store_memories(self, user_id: int, user_message: str, session: Session) -> None:
        """
        Extract meaningful information from user message and store as memories.
        
        Uses MemoryExtractor to intelligently identify facts, preferences, goals, etc.
        Automatically handles name, commitment, preferred times, etc.
        Also detects user's language from first message.
        
        Args:
            user_id: User ID from database
            user_message: The user's message
            session: SQLAlchemy session
        """
        try:
            # Detect language from user message (store/update when confident)
            if self.memory_manager:
                existing_lang = self.memory_manager.get_memory(user_id, "user_language")
                existing_value = existing_lang[0].get("value") if existing_lang else None
                try:
                    norwegian_keywords = [
                        "jeg heter", "hvordan går", "vær så snill", "god morgen", "god kveld", "god ettermiddag",
                    ]
                    norwegian_single_words = {
                        "hei", "jeg", "heter", "hvordan", "takk", "lyst", "ikke", "ja", "nei",
                    }
                    english_keywords = [
                        "good morning", "good evening", "good afternoon", "how are", "what is",
                    ]
                    english_single_words = {
                        "hello", "hi", "i", "you", "the", "and", "please", "thank",
                    }

                    msg_lower = user_message.lower()
                    tokens = re.findall(r"[a-zA-Z]+", msg_lower)
                    token_set = set(tokens)
                    word_count = len(user_message.split())
                    has_no_keywords = (
                        any(kw in msg_lower for kw in norwegian_keywords)
                        or any(kw in token_set for kw in norwegian_single_words)
                    )
                    has_en_keywords = (
                        any(kw in msg_lower for kw in english_keywords)
                        or any(kw in token_set for kw in english_single_words)
                    )
                    stripped_message = user_message.strip()
                    is_probable_name = (
                        word_count <= 2
                        and stripped_message[:1].isupper()
                        and stripped_message.replace(" ", "").isalpha()
                        and not (has_no_keywords or has_en_keywords)
                    )

                    detected_lang = None
                    # For very short inputs, prefer strong keyword hints
                    if word_count <= 3 and has_no_keywords:
                        detected_lang = "no"
                    elif word_count <= 3 and has_en_keywords:
                        detected_lang = "en"
                    # Avoid detection on very short messages unless strong keywords are present
                    elif word_count < 4 and not (has_no_keywords or has_en_keywords):
                        detected_lang = None
                    else:
                        try:
                            detected_lang = detect(user_message)
                        except LangDetectException:
                            if has_no_keywords:
                                detected_lang = "no"
                            elif has_en_keywords:
                                detected_lang = "en"

                    # Guard against NL misclassification when Norwegian keywords are present
                    if detected_lang in ["nl", "de", "sv", "da", "sl"] and has_no_keywords:
                        detected_lang = "no"

                    # Map language codes to full names
                    lang_names = {
                        "no": "Norwegian",
                        "nb": "Norwegian",
                        "nn": "Norwegian",
                        "en": "English",
                        "sv": "Swedish",
                        "da": "Danish",
                        "de": "German",
                        "fr": "French",
                        "es": "Spanish",
                        "it": "Italian",
                        "pt": "Portuguese",
                        "ru": "Russian",
                        "ja": "Japanese",
                        "zh-cn": "Chinese",
                    }
                    if not detected_lang:
                        lang_name = None
                    else:
                        lang_name = lang_names.get(detected_lang, detected_lang.upper())

                    should_update = False
                    if is_probable_name:
                        should_update = False
                    elif not existing_value and lang_name:
                        should_update = True
                    elif lang_name and lang_name != existing_value:
                        # Only update when message is long enough or contains strong keywords
                        if word_count >= 4 and (has_no_keywords or has_en_keywords):
                            should_update = True
                        elif has_no_keywords and lang_name == "Norwegian":
                            should_update = True
                        elif has_en_keywords and lang_name == "English":
                            should_update = True

                    if should_update:
                        self.memory_manager.store_memory(
                            user_id=user_id,
                            key="user_language",
                            value=lang_name,
                            confidence=0.9,
                            source="dialogue_engine_language_detection",
                            category="preference",
                        )
                        logger.info(f"Detected language for user {user_id}: {lang_name} (code: {detected_lang})")
                except LangDetectException as e:
                    logger.warning(f"Could not detect language: {e}")
            
            # Get user's existing memories for context
            user_context = None
            if self.memory_manager:
                existing_memories = {}
                for key in ["first_name", "acim_commitment", "learning_goal"]:
                    memories = self.memory_manager.get_memory(user_id, key)
                    if memories:
                        existing_memories[key] = memories[0].get("value")
                
                user_context = {
                    "user_id": user_id,
                    "existing_memories": existing_memories,
                } if existing_memories else None
            
            # Extract memories using Ollama
            extracted_memories = await self.memory_extractor.extract_memories(
                user_message, 
                user_context
            )
            
            # Store extracted memories
            for memory in extracted_memories:
                try:
                    self.memory_manager.store_memory(
                        user_id=user_id,
                        key=memory.get("key"),
                        value=memory.get("value"),
                        confidence=memory.get("confidence", 1.0),
                        ttl_hours=memory.get("ttl_hours"),
                        source="dialogue_engine_extractor",
                    )
                    logger.info(
                        f"Stored memory for user {user_id}: {memory.get('key')}="
                        f"{memory.get('value')[:50]}"
                    )
                except Exception as e:
                    logger.error(f"Error storing memory: {e}")
        
        except Exception as e:
            logger.error(f"Error in memory extraction: {e}")

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

                        lesson = session.query(Lesson).filter(Lesson.lesson_id == 1).first()
                        if lesson:
                            language = self._get_user_language(user_id)
                            welcome_msg = self.onboarding.get_lesson_1_welcome_message(user_id)
                            lesson_msg = await self._format_lesson_message(lesson, language)
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

                        lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
                        if lesson:
                            language = self._get_user_language(user_id)
                            continuation_msg = self.onboarding.get_continuation_welcome_message(user_id, lesson_id)
                            lesson_msg = await self._format_lesson_message(lesson, language)
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

    def _delete_user(self, user_id: int) -> None:
        """
        Delete a user and all associated data from the database.
        Called when user declines consent during onboarding.
        
        Deletes:
        - All memories associated with user
        - All message logs
        - All schedules
        - The user record itself
        """
        if not self.db:
            return
        
        try:
            from src.models.database import Memory, Schedule, MessageLog, User
            
            # Delete in correct order due to foreign keys
            self.db.query(Memory).filter_by(user_id=user_id).delete(synchronize_session=False)
            self.db.query(Schedule).filter_by(user_id=user_id).delete(synchronize_session=False)
            self.db.query(MessageLog).filter_by(user_id=user_id).delete(synchronize_session=False)
            self.db.query(User).filter_by(user_id=user_id).delete(synchronize_session=False)
            
            self.db.commit()
            logger.info(f"[User deleted] User {user_id} deleted due to declined consent")
        except Exception as e:
            logger.error(f"[User deletion error] Failed to delete user {user_id}: {e}")
            self.db.rollback()

    def _detect_lesson_request(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Detect if user is requesting information about a specific lesson.
        
        Examples:
        - "Tell me about lesson 10"
        - "What is lesson 5?"
        - "Explain lesson 42"
        - "Lesson 1 content"
        
        Returns:
            Dict with lesson_id if detected, None otherwise
        """
        text_lower = text.lower()
        
        # Pattern: mention of "lesson" + number
        import re
        lesson_patterns = [
            r'lesson\s+(\d+)',
            r'day\s+(\d+)',
            r'lesson\s+#(\d+)',
            r'#(\d+)',
        ]
        
        for pattern in lesson_patterns:
            match = re.search(pattern, text_lower)
            if match:
                lesson_num = int(match.group(1))
                # Validate lesson is within valid range (1-365 for ACIM)
                if 1 <= lesson_num <= 365:
                    return {"lesson_id": lesson_num}
        
        return None

    async def _handle_lesson_request(self, lesson_id: int, user_input: str, session: Session) -> str:
        """
        Handle requests for specific lesson content using RAG.
        
        Retrieves the lesson from database and injects it into the context
        so the LLM responds with accurate information.
        """
        if not self.db:
            return "I couldn't retrieve that lesson right now."
        
        try:
            # Fetch the lesson from database
            lesson = session.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
            
            if not lesson:
                return f"I couldn't find lesson {lesson_id} in my database. ACIM has 365 lessons - please ask for a lesson between 1 and 365."
            
            # Build RAG-enhanced prompt with lesson content
            system_prompt = f"""{settings.SYSTEM_PROMPT}

### Requested Lesson Content [RAG CONTEXT - USE THIS]
**Lesson {lesson.lesson_id}**: "{lesson.title}"

{lesson.content}

---
The user is asking about this lesson. Use the above content to provide accurate, detailed information."""
            
            # Build the prompt with lesson context
            prompt = f"""{system_prompt}

### User Question
{user_input}

### Response
Provide a thoughtful, detailed response about this ACIM lesson. Reference specific points from the lesson content above. Be warm and encouraging."""
            
            # Call Ollama with lesson-injected context
            response = await self.call_ollama(prompt)
            return response
            
        except Exception as e:
            logger.error(f"[Lesson request error] Failed to handle lesson {lesson_id}: {e}")
            return f"I encountered an error retrieving lesson {lesson_id}. Please try again."

    def get_onboarding_prompt(self) -> str:
        """
        Return onboarding prompt sequence for new users.
        """
        if not self.prompt_builder:
            return "Welcome! What's your name?"
        
        return self.prompt_builder.build_onboarding_prompt(settings.SYSTEM_PROMPT)
