import httpx
import logging
import json
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from langdetect import detect, LangDetectException
from src.services.memory_manager import MemoryManager
from src.services.trigger_matcher import get_trigger_matcher
from src.services.trigger_dispatcher import get_trigger_dispatcher
from src.services.prompt_builder import PromptBuilder
from src.services.semantic_search import get_semantic_search_service
from src.services.memory_extractor import MemoryExtractor
from src.services.onboarding_service import OnboardingService
from src.services.onboarding.flow import OnboardingFlow
from src.services.scheduler import SchedulerService
from src.services.dialogue import (
    call_ollama,
    detect_lesson_request,
    handle_lesson_request,
    format_lesson_message,
    translate_text,
    handle_lesson_confirmation,
    handle_schedule_messages,
    get_user_language,
    detect_and_store_language,
    extract_and_store_memories,
    handle_rag_mode_toggle,
    parse_rag_prefix,
    is_rag_mode_enabled,
    handle_forget_commands,
    handle_gdpr_commands,
    handle_debug_next_day,
    maybe_send_next_lesson,
)
from src.config import settings
from src.models.database import User
from src.services.timezone_utils import ensure_user_timezone, format_dt_in_timezone

logger = logging.getLogger(__name__)

class DialogueEngine:
    def __init__(self, db: Optional[Session] = None, memory_manager: Optional[MemoryManager] = None):
        self.db = db
        self.memory_manager = memory_manager or MemoryManager(db)
        self.prompt_builder = PromptBuilder(db, self.memory_manager) if db else None
        self.memory_extractor = MemoryExtractor()
        self.onboarding = OnboardingService(db) if db else None
        self.onboarding_flow = (
            OnboardingFlow(self.memory_manager, self.onboarding, self.call_ollama)
            if self.onboarding
            else None
        )

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
        user = session.query(User).filter_by(user_id=user_id).first()
        if not user:
            return "User not found."

        # Keep original user text for trigger matching
        original_text = text
        gdpr_response = await handle_gdpr_commands(
            text=text,
            session=session,
            user_id=user_id,
            channel=user.channel,
        )
        if gdpr_response:
            return gdpr_response

        if user.is_deleted:
            return "Your data has been deleted. If you want to start again, please re-register."
        if user.processing_restricted or not user.opted_in:
            return "Your data processing is restricted. If you want to resume, please update your consent settings."

        # Handle RAG mode toggle: rag_mode on/off
        rag_toggle_response = handle_rag_mode_toggle(text, self.memory_manager, user_id)
        if rag_toggle_response:
            return rag_toggle_response

        # Detect RAG prefix: "rag my question" or "rag: my question"
        text, use_rag_for_this_message = parse_rag_prefix(text)

        # Check if RAG mode is persistently enabled
        if not use_rag_for_this_message and self.memory_manager:
            use_rag_for_this_message = is_rag_mode_enabled(self.memory_manager, user_id)

        # Handle forget commands (semantic memory deletion)
        forget_response = await handle_forget_commands(
            text,
            self.memory_manager,
            session,
            user_id,
        )
        if forget_response:
            return forget_response

        # Debug magic command: simulate next day for lesson progression
        debug_response = handle_debug_next_day(
            text,
            self.memory_manager,
            session,
            user_id,
        )
        if debug_response:
            return debug_response

        # FIRST: Extract memories from user message (this might store commitment, name, time, etc.)
        await extract_and_store_memories(
            self.memory_manager, self.memory_extractor, user_id, text, rag_mode=use_rag_for_this_message
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

        # Check if user is asking about a specific lesson (run regardless of onboarding)
        lesson_request = detect_lesson_request(text)
        if lesson_request:
            # Determine user language to decide whether to return raw lesson text
            user_lang = get_user_language(self.memory_manager, user_id) if self.memory_manager else "english"
            lesson_response = await handle_lesson_request(
                lesson_request["lesson_id"], text, session, user_language=user_lang
            )
            if lesson_response:
                return lesson_response

        # Handle schedule follow-ups (e.g., user clarifying a previous deferred schedule request)
        schedule_response = await handle_schedule_messages(
            user_id=user_id,
            text=text,
            session=session,
            memory_manager=self.memory_manager,
            onboarding_service=self.onboarding,
            schedule_request_handler=self._handle_schedule_request,
            call_ollama=self.call_ollama,
        )
        if schedule_response:
            return schedule_response

        # Schedule handled after LLM response via trigger matching; skip pre-LLM scheduling
        
        # Check if user needs onboarding (new users)
        if self.onboarding_flow and self.onboarding.should_show_onboarding(user_id):
            onboarding_response = await self.onboarding_flow.handle_onboarding(user_id, text, session)
            if onboarding_response:
                return onboarding_response

        # Auto-send next lesson on a new day when user makes contact
        if include_lesson and self.prompt_builder and not use_rag_for_this_message:
            auto_message = await maybe_send_next_lesson(
                user_id=user_id,
                text=text,
                session=session,
                prompt_builder=self.prompt_builder,
                memory_manager=self.memory_manager,
                call_ollama=self.call_ollama,
            )
            if auto_message:
                return auto_message
        
        # Regular conversation
        if not self.prompt_builder:
            # Fallback for cases without DB session
            prompt = f"{settings.SYSTEM_PROMPT}\nUser: {text}\n\nAssistant:"
        else:
            # Build context-aware prompt
            relevant_memories = []
            try:
                search_service = get_semantic_search_service()
                # Use a fresh session for semantic search to avoid lock conflicts
                search_session = Session(bind=session.get_bind())
                try:
                    results = await search_service.search_memories(
                        user_id=user_id,
                        query_text=text,
                        session=search_session,
                    )
                    relevant_memories = [
                        {
                            "memory_id": memory.memory_id,
                            "key": memory.key,
                            "value": memory.value,
                            "category": memory.category,
                            "confidence": memory.confidence,
                            "similarity": score,
                        }
                        for memory, score in results
                    ]
                    # If this message is explicitly using RAG, remove transient lesson
                    # context such as `current_lesson` — RAG mode should rely only on
                    # semantic search results and not inject the active lesson state.
                    if use_rag_for_this_message:
                        relevant_memories = [m for m in relevant_memories if m.get("key") != "current_lesson"]
                finally:
                    search_session.close()
            except Exception as ex:
                logger.warning(f"Semantic search failed: {ex}")

            # Use RAG prompt if RAG mode is active for this message
            if use_rag_for_this_message:
                system_prompt = settings.SYSTEM_PROMPT_RAG
                prompt = self.prompt_builder.build_rag_prompt(
                    user_id=user_id,
                    user_input=text,
                    system_prompt=system_prompt,
                    relevant_memories=relevant_memories,
                    include_conversation_history=include_history,
                    history_turns=history_turns,
                )
            else:
                system_prompt = settings.SYSTEM_PROMPT
                prompt = self.prompt_builder.build_prompt(
                    user_id=user_id,
                    user_input=text,
                    system_prompt=system_prompt,
                    include_lesson=include_lesson,
                    include_conversation_history=include_history,
                    history_turns=history_turns,
                    relevant_memories=relevant_memories,
                )
        
        # Call Ollama
        rag_model = settings.OLLAMA_CHAT_RAG_MODEL or settings.OLLAMA_MODEL
        response = await self.call_ollama(prompt, model=rag_model if use_rag_for_this_message else None)
        if response is None:
            logger.warning("LLM returned None; coercing to placeholder string")
            response = "[No response from LLM]"
        # Trigger matching and dispatch (always enabled)
        from src.services.triggering import handle_triggers

        await handle_triggers(response=response, original_text=original_text, session=session, memory_manager=self.memory_manager, user_id=user_id)

        return response



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
            tz_name = ensure_user_timezone(
                self.memory_manager,
                user_id,
                get_user_language(self.memory_manager, user_id),
                source="dialogue_engine_schedule_status",
            )
            if schedule.next_send_time:
                local_dt, _ = format_dt_in_timezone(schedule.next_send_time, tz_name)
                time_display = f"{local_dt:%H:%M}"
            else:
                time_display = "(time not set)"
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

You have a daily reminder for {time_display}.

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

            tz_name = ensure_user_timezone(
                self.memory_manager,
                user_id,
                get_user_language(self.memory_manager, user_id),
                source="dialogue_engine_schedule_create",
            )
            if schedule.next_send_time:
                local_dt, _ = format_dt_in_timezone(schedule.next_send_time, tz_name)
                time_display = f"{local_dt:%H:%M}"
            else:
                hour, minute = SchedulerService.parse_time_string(time_str)
                time_display = f"{hour:02d}:{minute:02d}"

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

I've scheduled your daily ACIM lesson for {time_display} each day.

Each day at this time, I'll send you one lesson. Remember: consistency is key. Even if you can only spend 5 minutes with the lesson, that daily practice will transform your perception.

Your first lesson will arrive tomorrow at {time_display}. 🙏"""

        except Exception as e:
            logger.error(f"Error creating schedule: {e}")
            return "I had trouble setting up your schedule. Could you tell me your preferred time? (e.g., '9:00 AM' or 'morning')"


    def get_onboarding_prompt(self) -> str:
        """
        Return onboarding prompt sequence for new users.
        """
        if not self.prompt_builder:
            return "Welcome! What's your name?"
        
        return self.prompt_builder.build_onboarding_prompt(settings.SYSTEM_PROMPT)
