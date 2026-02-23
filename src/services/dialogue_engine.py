import logging
from typing import Optional
from sqlalchemy.orm import Session
from src.memories import MemoryManager
from src.language.prompt_builder import PromptBuilder
from src.memories.semantic_search import get_semantic_search_service
from src.memories import MemoryExtractor
from src.onboarding.service import OnboardingService
from src.onboarding.flow import OnboardingFlow
from src.scheduler import SchedulerService
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
    handle_rag_prompt_command,
    parse_rag_prefix,
    is_rag_mode_enabled,
    handle_forget_commands,
    handle_gdpr_commands,
    handle_debug_next_day,
    maybe_send_next_lesson,
    handle_list_memories,
)
from src.lessons.handler import process_lesson_query
from src.config import settings
from src.models.database import User, Lesson
from src.memories.constants import MemoryCategory, MemoryKey
from src.services.timezone_utils import ensure_user_timezone, format_dt_in_timezone
from src.language.prompt_registry import get_prompt_registry

logger = logging.getLogger(__name__)

class DialogueEngine:
    def __init__(self, db: Optional[Session] = None, memory_manager: Optional[MemoryManager] = None):
        self.db = db
        self.memory_manager = memory_manager or MemoryManager(db)
        self.prompt_registry = get_prompt_registry()
        self.prompt_builder = PromptBuilder(db, self.memory_manager) if db else None
        self.memory_extractor = MemoryExtractor()
        self.onboarding = OnboardingService(db) if db else None
        self.onboarding_flow = (
            OnboardingFlow(self.memory_manager, self.onboarding, self.call_ollama)
            if self.onboarding
            else None
        )
    
    def get_trigger_dispatcher(self, db=None, memory_manager: MemoryManager = None) -> object:
        from src.triggers import get_trigger_dispatcher as _get
        return _get(db=db, memory_manager=memory_manager)

    async def call_ollama(self, prompt: str, model: Optional[str] = None, language: Optional[str] = None) -> str:
        """Delegate to dialogue.ollama_client with optional language hint."""
        return await call_ollama(prompt, model, language)

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

        user_lang = await detect_and_store_language(self.memory_manager, user_id, text)

        # Handle RAG mode toggle: rag_mode on/off
        rag_toggle_response = handle_rag_mode_toggle(text, self.memory_manager, user_id)
        if rag_toggle_response:
            return rag_toggle_response

        # Detect RAG prefix: "rag my question" or "rag: my question"
        text, use_rag_for_this_message = parse_rag_prefix(text)

        # Check if RAG mode is persistently enabled
        if not use_rag_for_this_message and self.memory_manager:
            use_rag_for_this_message = is_rag_mode_enabled(self.memory_manager, user_id)

        # If user is in RAG mode and asked to list memories, return full list
        if use_rag_for_this_message:
            list_memories = handle_list_memories(text, self.memory_manager, session, user_id)
            if list_memories:
                return list_memories

            # Handle RAG prompt management commands: rag_prompt list|select|custom|show
            prompt_cmd_response = handle_rag_prompt_command(text, self.memory_manager, user_id)
            if prompt_cmd_response:
                return prompt_cmd_response


        # Handle schedule deletion confirmation/commands (ask for confirmation first)
        from src.services.dialogue import handle_schedule_deletion_commands

        deletion_response = await handle_schedule_deletion_commands(
            text,
            self.memory_manager,
            session,
            user_id,
        )
        if deletion_response:
            return deletion_response

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
        # Run extraction early so simple factual replies during onboarding (e.g., "My name is Johannes")
        # are captured and persisted before onboarding flow generates follow-ups.
        if self.onboarding_flow:
            await extract_and_store_memories(
                self.memory_manager, self.memory_extractor, user_id, text, rag_mode=use_rag_for_this_message
            )

        # If user needs onboarding, handle onboarding now to prioritise pending
        # onboarding prompts (e.g., consent, lesson-status) after extraction.
        if (
            self.onboarding_flow
            and self.onboarding.should_show_onboarding(user_id)
            and not use_rag_for_this_message
        ):
            onboarding_response = await self.onboarding_flow.handle_onboarding(user_id, text, session)
            if onboarding_response:
                return onboarding_response
 

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

        # Handle lesson-related queries via the dedicated handler
        lesson_resp = await process_lesson_query(
            user_id=user_id,
            text=text,
            session=session,
            prompt_builder=self.prompt_builder,
            memory_manager=self.memory_manager,
            onboarding_flow=self.onboarding_flow,
            onboarding_service=self.onboarding,
            user_language=user_lang,
        )
        if lesson_resp:
            return lesson_resp

        # Handle schedule follow-ups (e.g., user clarifying a previous deferred schedule request)
        schedule_response = await handle_schedule_messages(
            user_id=user_id,
            text=text,
            session=session,
            memory_manager=self.memory_manager,
            onboarding_service=self.onboarding,
            schedule_request_handler=self._handle_schedule_request,
            call_ollama=self.call_ollama,
            use_rag_for_this_message=use_rag_for_this_message,
        )
        if schedule_response:
            return schedule_response

        # Schedule handled after LLM response via trigger matching; skip pre-LLM scheduling

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
            # Compute the user's query embedding once for this turn so it can
            # be reused by semantic search and later trigger matching.
            from src.services.embedding_service import get_embedding_service
            user_text_embedding = await get_embedding_service().generate_embedding(text)

            # Guard semantic search: failures in the search backend or embedding
            # generation should not crash the whole message turn. Also ensure
            # the search_session is closed in all cases.
            try:
                search_service = get_semantic_search_service()
                # Use a fresh session for semantic search to avoid lock conflicts
                search_session = Session(bind=session.get_bind())
                try:
                    results = await search_service.search_memories(
                        user_id=user_id,
                        query_text=text,
                        session=search_session,
                        query_embedding=user_text_embedding,
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
                finally:
                    search_session.close()
            except Exception as ex:
                # Log and continue — semantic search is optional context.
                logger.warning(f"Semantic search failed: {ex}")

            # Use RAG prompt if RAG mode is active for this message
            if use_rag_for_this_message:
                # Resolve per-user prompt via PromptRegistry (falls back to SYSTEM_PROMPT_RAG)
                # Prompt registry may fail (database/unexpected errors). Fall
                # back to the default RAG system prompt rather than raising.
                try:
                    system_prompt = self.prompt_registry.get_prompt_for_user(self.memory_manager, user_id)
                except Exception:
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
        
        # Run trigger matching on original user text before calling the LLM.
        from src.lessons.handler import pre_llm_lesson_short_circuit

        pre = await pre_llm_lesson_short_circuit(
            original_text=text,
            precomputed_embedding=user_text_embedding,
            user_id=user_id,
            session=session,
            prompt_builder=self.prompt_builder,
            user_lang=user_lang,
        )
        if pre:
            return pre

        response = await self.call_ollama(
            prompt, model=settings.OLLAMA_CHAT_RAG_MODEL if use_rag_for_this_message else None, language=user_lang
        )
        if response is None:
            logger.warning("LLM returned None; coercing to placeholder string")
            response = "[No response from LLM]"
        # Trigger matching and dispatch (always enabled)
        from src.triggers.triggering import handle_triggers

        await handle_triggers(
            response=response,
            original_text=text,
            session=session,
            memory_manager=self.memory_manager,
            user_id=user_id,
            original_text_embedding=user_text_embedding,
        )

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
            # Use the schedule query response builder to list all active reminders
            from src.scheduler.schedule_query_handler import build_schedule_status_response

            tz_name = ensure_user_timezone(
                self.memory_manager,
                user_id,
                get_user_language(self.memory_manager, user_id),
                source="dialogue_engine_schedule_status",
            )

            resp_text = build_schedule_status_response(schedules, tz_name)
            # Clear any pending flag and translate if necessary
            if self.memory_manager:
                self.memory_manager.store_memory(
                    user_id=user_id,
                    key=MemoryKey.SCHEDULE_REQUEST_PENDING,
                    value="false",
                    confidence=1.0,
                    source="dialogue_engine",
                    ttl_hours=1,
                    category=MemoryCategory.CONVERSATION.value,
                )

            user_lang = get_user_language(self.memory_manager, user_id)
            if user_lang and user_lang.lower() not in ("en",):
                resp_text = await translate_text(resp_text, user_lang, self.call_ollama)

            return resp_text

        # Check if they have a preferred time stored
        time_memories = self.memory_manager.get_memory(user_id, MemoryKey.PREFERRED_LESSON_TIME)

        if not time_memories:
            # Ask for their preferred time
            if self.memory_manager:
                self.memory_manager.store_memory(
                    user_id=user_id,
                    key=MemoryKey.SCHEDULE_REQUEST_PENDING,
                    value="true",
                    confidence=1.0,
                    source="dialogue_engine",
                    ttl_hours=1,
                    category=MemoryCategory.CONVERSATION.value,
                )
            return """Great! I'll set up daily reminders for your ACIM lessons.

When would you like to receive them? (e.g., "9:00 AM", "morning", "evening", "8:30 PM")"""

        # They have a time preference - create the schedule
        time_str = time_memories[0]["value"]

        # Wrap schedule creation in a try/except so transient errors in the
        # scheduler or timezone resolution return a helpful message to the
        # user instead of raising an uncaught exception.
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

            name_memories = self.memory_manager.get_memory(user_id, MemoryKey.FIRST_NAME)
            name = name_memories[0]["value"] if name_memories else "friend"

            if self.memory_manager:
                self.memory_manager.store_memory(
                    user_id=user_id,
                    key=MemoryKey.SCHEDULE_REQUEST_PENDING,
                    value="false",
                    confidence=1.0,
                    source="dialogue_engine",
                    ttl_hours=1,
                    category=MemoryCategory.CONVERSATION.value,
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


# Module-level wrapper so tests can monkeypatch `src.services.dialogue_engine.get_trigger_dispatcher`
def get_trigger_dispatcher(db=None, memory_manager: MemoryManager = None) -> object:
    from src.triggers import get_trigger_dispatcher as _get
    return _get(db=db, memory_manager=memory_manager)
