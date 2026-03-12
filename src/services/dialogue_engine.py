import logging
from typing import Optional, Union
from sqlalchemy.orm import Session
from src.memories import MemoryManager
from src.language.prompt_builder import PromptBuilder
from src.memories.semantic_search import get_semantic_search_service
from src.onboarding.service import OnboardingService
from src.onboarding.flow import OnboardingFlow
from src.scheduler import api as scheduler_api
from src.services.dialogue import (
    call_ollama,
    stream_ollama,
    format_lesson_message,
    translate_text,
    handle_schedule_messages,
    get_user_language,
    detect_and_store_language,
    handle_rag_mode_toggle,
    handle_rag_prompt_command,
    parse_rag_prefix,
    is_rag_mode_enabled,
    handle_forget_commands,
    handle_gdpr_commands,
    maybe_send_next_lesson,
    handle_list_memories,
)
from src.config import settings
from src.models.database import User, Lesson
from src.memories.constants import MemoryCategory, MemoryKey
from src.core.timezone import get_user_timezone_from_db, format_dt_in_timezone
from src.language.prompt_registry import get_prompt_registry

logger = logging.getLogger(__name__)

class DialogueEngine:
    def __init__(self, db: Optional[Session] = None, memory_manager: Optional[MemoryManager] = None):
        if db is None:
            raise ValueError("DialogueEngine requires an active DB session")

        self.db = db
        self.memory_manager = memory_manager or MemoryManager(db)
        self.prompt_registry = get_prompt_registry()
        self.prompt_builder = PromptBuilder(db, self.memory_manager)
        self.onboarding = OnboardingService(db)
        self.onboarding_flow = OnboardingFlow(self.memory_manager, self.onboarding, self.call_ollama)

    @property
    def memory_judge(self):
        """Expose MemoryJudge from memory_manager for memory extraction."""
        return self.memory_manager.ai_judge
    
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
    ) -> dict:
        """
        Process user message with full context awareness.
        """
        user = session.query(User).filter_by(user_id=user_id).first()
        if not user:
            return "User not found."

        # 1. Restrictions and GDPR
        restriction_response = await self._check_user_restrictions(user_id, text, user, session)
        if restriction_response:
            return restriction_response

        user_lang = await detect_and_store_language(self.memory_manager, user_id, text)

        # 2. RAG and Language Setup
        text, use_rag_for_this_message, rag_response = self._setup_rag_configuration(user_id, text)
        if rag_response:
            return rag_response

        # 3. Command Handling (RAG management, Schedule deletion, Forget, Debug)
        command_response = await self._handle_commands(user_id, text, session, use_rag_for_this_message)
        if command_response:
            return command_response

        # 4. Memory Extraction and Onboarding
        onboarding_response = await self._handle_onboarding_stage(user_id, text, session, use_rag_for_this_message)
        if onboarding_response:
            return onboarding_response

        # 5. Lesson and Schedule logic
        lesson_schedule_response = await self._handle_lesson_and_schedule_stage(
            user_id, text, session, user_lang, include_lesson, use_rag_for_this_message
        )
        if lesson_schedule_response:
            return lesson_schedule_response

        # ALWAYS STREAM: no sync fallback
        return await self._generate_llm_response_streaming(
            user_id, text, session, user_lang, use_rag_for_this_message, include_history, history_turns, include_lesson
        )

    async def _check_user_restrictions(self, user_id: int, text: str, user: User, session: Session) -> Optional[str]:
        """Handle GDPR commands and check if user is deleted or restricted."""
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
        return None

    def _setup_rag_configuration(self, user_id: int, text: str) -> tuple[str, bool, Optional[str]]:
        """Detect and configure RAG mode for the current message."""
        # Handle RAG mode toggle: rag_mode on/off
        rag_toggle_response = handle_rag_mode_toggle(text, self.memory_manager, user_id)
        if rag_toggle_response:
            return text, False, rag_toggle_response

        # Detect RAG prefix: "rag my question" or "rag: my question"
        text, use_rag = parse_rag_prefix(text)

        # Check if RAG mode is persistently enabled
        if not use_rag and self.memory_manager:
            use_rag = is_rag_mode_enabled(self.memory_manager, user_id)
        
        return text, use_rag, None

    async def _handle_commands(self, user_id: int, text: str, session: Session, use_rag: bool) -> Optional[str]:
        """Handle various specialized commands (RAG management, schedule deletion, etc.)."""
        # If user is in RAG mode and asked to list memories, return full list
        if use_rag:
            list_memories = handle_list_memories(text, self.memory_manager, session, user_id)
            if list_memories:
                return list_memories

            # Handle RAG prompt management commands: rag_prompt list|select|custom|show
            prompt_cmd_response = handle_rag_prompt_command(text, self.memory_manager, user_id)
            if prompt_cmd_response:
                return prompt_cmd_response

        # Handle forget commands (semantic memory deletion) - only in RAG mode
        forget_response = await handle_forget_commands(
            text, self.memory_manager, session, user_id, use_rag
        )
        if forget_response:
            return forget_response

        return None

    async def _handle_onboarding_stage(self, user_id: int, text: str, session: Session, use_rag: bool) -> Optional[str]:
        """Handle onboarding flow."""
        # Note: Memory extraction now happens via extract_memory function in the function calling system
        # The LLM will extract memories as part of its response, not as a separate call

        # Handle onboarding flow if needed
        if (
            self.onboarding_flow
            and self.onboarding.should_show_onboarding(user_id)
            and not use_rag
        ):
            # Check if there's a pending step before handling
            from src.memories.constants import MemoryKey
            pending_step = self.memory_manager.get_memory(user_id, MemoryKey.ONBOARDING_STEP_PENDING)
            pending_step_value = str(pending_step[0].get("value", "")).lower() if pending_step else None
            
            onboarding_response = await self.onboarding_flow.handle_onboarding(user_id, text, session)
            
            return onboarding_response
        
        return None

    async def _handle_lesson_and_schedule_stage(
        self, user_id: int, text: str, session: Session, user_lang: str, include_lesson: bool, use_rag: bool
    ) -> Optional[str]:
        # Handle schedule follow-ups
        schedule_response = await handle_schedule_messages(
            user_id=user_id,
            text=text,
            session=session,
            memory_manager=self.memory_manager,
            onboarding_service=self.onboarding,
            schedule_request_handler=self._handle_schedule_request,
            call_ollama=self.call_ollama,
            use_rag_for_this_message=use_rag,
        )
        if schedule_response:
            return schedule_response

        # Auto-send next lesson on a new day when user makes contact
        if include_lesson and not use_rag:
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
        
        return None

    async def _generate_llm_response(
        self,
        user_id: int,
        text: str,
        session: Session,
        user_lang: str,
        use_rag: bool,
        include_history: bool,
        history_turns: int,
        include_lesson: bool,
    ) -> str:
        """Build prompt, call LLM, and handle post-response triggers."""
        # Build context-aware prompt
        # Note: No longer generating embeddings for trigger matching - using function calling instead
        relevant_memories = await self._get_relevant_memories(user_id, text, session)

        # Detect context type for function availability
        context_type = self._detect_context_type(user_id, text, use_rag)

        # Use RAG prompt if RAG mode is active for this message
        if use_rag:
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
                context_type=context_type,
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
                context_type=context_type,
            )
        
        # Note: Removed pre_llm_lesson_short_circuit with embedding parameter
        # Lesson handling now happens via function calling

        response = await self.call_ollama(
            prompt, model=settings.OLLAMA_CHAT_RAG_MODEL if use_rag else None, language=user_lang
        )
        if response is None:
            logger.warning("LLM returned None; coercing to placeholder string")
            response = "[No response from LLM]"

        # Trigger matching and dispatch using function calling (always enabled)
        from src.triggers.triggering import handle_triggers

        trigger_diagnostics = await handle_triggers(
            response=response,
            original_text=text,
            session=session,
            memory_manager=self.memory_manager,
            user_id=user_id,
        )

        # Parse the response to extract just the text (not the full JSON with functions)
        from src.functions.intent_parser import get_intent_parser
        parser = get_intent_parser()
        parse_result = parser.parse(response)
        
        # Build final response combining AI text with function results
        from src.functions.response_builder import get_response_builder
        response_builder = get_response_builder()
        
        execution_result = trigger_diagnostics.get("execution_result") if trigger_diagnostics else None
        if execution_result:
            built_response = response_builder.build(
                user_text=text,
                ai_response_text=parse_result.response_text if parse_result.response_text is not None else response,
                execution_result=execution_result,
                include_function_results=True,
            )
            return built_response.text
        
        # Return only the natural language response, not the full JSON
        # Use parsed response text if available (even if empty string), otherwise fall back to raw response
        if parse_result.success and parse_result.response_text is not None:
            return parse_result.response_text
        return response

    def _detect_context_type(self, user_id: int, text: str, use_rag: bool) -> str:
        """Detect the conversation context type for function availability."""
        # Check for RAG mode
        if use_rag:
            return "rag"
        
        # Check for specific onboarding stage first (granular context)
        from src.memories.constants import MemoryKey
        from src.functions.definitions import FunctionDefinitions
        pending_step = self.memory_manager.get_memory(user_id, MemoryKey.ONBOARDING_STEP_PENDING)
        if pending_step:
            step_value = str(pending_step[0].get("value", "")).lower()
            # Use centralized stage map from FunctionDefinitions (DRY)
            if step_value in FunctionDefinitions.ONBOARDING_STAGE_MAP:
                return FunctionDefinitions.ONBOARDING_STAGE_MAP[step_value]
        
        # Check if user is in general onboarding (no specific pending step)
        if self.onboarding and self.onboarding.should_show_onboarding(user_id):
            return "onboarding"
        
        # Check for schedule-related keywords
        schedule_keywords = ["schedule", "reminder", "time", "daily", "lesson time"]
        text_lower = text.lower()
        if any(kw in text_lower for kw in schedule_keywords):
            return "schedule_setup"
        
        # Default to general chat
        return "general_chat"

    async def _get_relevant_memories(self, user_id: int, text: str, session: Session) -> list:
        """Retrieve relevant memories for the current context."""
        relevant_memories = []
        try:
            search_service = get_semantic_search_service()
            search_session = Session(bind=session.get_bind())
            try:
                # Note: No longer requires pre-computed embedding
                # The semantic search service will generate embedding internally if needed
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
                        "similarity": score,
                    }
                    for memory, score in results
                ]
            finally:
                search_session.close()
        except Exception as ex:
            logger.warning(f"Semantic search failed: {ex}")
        return relevant_memories

    async def _handle_schedule_request(self, user_id: int, text: str, session: Session) -> Optional[str]:
        """
        Handle explicit schedule/reminder requests.
        """
        # Check if user already has commitment
        #status = self.onboarding.get_onboarding_status(user_id)
        #
        #if not status["has_commitment"]:
        #    # Need commitment first
        #    return self.onboarding.get_onboarding_prompt(user_id)
        
        # Check if they already have a schedule
        schedules = scheduler_api.get_user_schedules(user_id, session=session)
        if schedules:
            # Use the schedule query response builder to list all active reminders
            from src.scheduler.schedule_query_handler import build_schedule_status_response

            tz_name = get_user_timezone_from_db(self.db.object_session, user_id)

            resp_text = build_schedule_status_response(schedules, tz_name)
            # Clear any pending flag and translate if necessary
            if self.memory_manager:
                self.memory_manager.store_memory(
                    user_id=user_id,
                    key=MemoryKey.SCHEDULE_REQUEST_PENDING,
                    value="false",
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
            schedule = scheduler_api.create_daily_schedule(
                user_id=user_id,
                lesson_id=None,
                time_str=time_str,
                session=session,
            )

            tz_name = get_user_timezone_from_db(self.db.object_session, user_id)
            if schedule.next_send_time:
                local_dt, _ = format_dt_in_timezone(schedule.next_send_time, tz_name)
                time_display = f"{local_dt:%H:%M}"
            else:
                hour, minute = scheduler_api.parse_time_string(time_str)
                time_display = f"{hour:02d}:{minute:02d}"

            name_memories = self.memory_manager.get_memory(user_id, MemoryKey.FIRST_NAME)
            name = name_memories[0]["value"] if name_memories else "friend"

            if self.memory_manager:
                self.memory_manager.store_memory(
                    user_id=user_id,
                    key=MemoryKey.SCHEDULE_REQUEST_PENDING,
                    value="false",
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
        return self.prompt_builder.build_onboarding_prompt(settings.SYSTEM_PROMPT)

    async def process_message_for_telegram(
        self,
        user_id: int,
        text: str,
        session: Session,
        chat_id: int,
        include_history: bool = True,
        history_turns: int = 4,
        include_lesson: bool = True,
    ) -> dict:
        """Process a user message and return either a plain string or a streaming context.

        Returns a dict with:
            - ``{"type": "text", "text": str}`` for non-LLM responses (commands,
              onboarding, lessons, schedules, etc.) that should be sent normally.
            - ``{"type": "stream", "generator": AsyncIterator[str], "post_hook": Callable}``
              when the response should be streamed token-by-token.  After the
              generator is exhausted the caller must invoke ``post_hook(full_text)``
              to run trigger matching and any remaining bookkeeping.
        """
        user = session.query(User).filter_by(user_id=user_id).first()
        if not user:
            return {"type": "text", "text": "User not found."}

        # 1. Restrictions and GDPR
        restriction_response = await self._check_user_restrictions(user_id, text, user, session)
        if restriction_response:
            return {"type": "text", "text": restriction_response}

        user_lang = await detect_and_store_language(self.memory_manager, user_id, text)

        # 2. RAG and Language Setup
        text, use_rag_for_this_message, rag_response = self._setup_rag_configuration(user_id, text)
        if rag_response:
            return {"type": "text", "text": rag_response}

        # 3. Command Handling
        command_response = await self._handle_commands(user_id, text, session, use_rag_for_this_message)
        if command_response:
            return {"type": "text", "text": command_response}

        # 4. Memory Extraction and Onboarding
        onboarding_response = await self._handle_onboarding_stage(user_id, text, session, use_rag_for_this_message)
        if onboarding_response:
            return {"type": "text", "text": onboarding_response}

        # 5. Lesson and Schedule logic
        lesson_schedule_response = await self._handle_lesson_and_schedule_stage(
            user_id, text, session, user_lang, include_lesson, use_rag_for_this_message
        )
        if lesson_schedule_response:
            return {"type": "text", "text": lesson_schedule_response}

        # 6. Core LLM Response — this is the streaming path
        return await self._generate_llm_response_streaming(
            user_id, text, session, user_lang, use_rag_for_this_message,
            include_history, history_turns, include_lesson,
        )

    async def _generate_llm_response_streaming(
        self,
        user_id: int,
        text: str,
        session: Session,
        user_lang: str,
        use_rag: bool,
        include_history: bool,
        history_turns: int,
        include_lesson: bool,
    ) -> dict:
        """Build prompt and return a streaming context dict.

        For English users the LLM response is streamed directly.
        For non-English users the LLM response is fetched in full first,
        then the *translation* call is streamed.
        """
        # Note: No longer generating embeddings for trigger matching - using function calling instead
        relevant_memories = await self._get_relevant_memories(user_id, text, session)

        # Detect context type for function availability
        context_type = self._detect_context_type(user_id, text, use_rag)

        # Build prompt (same logic as _generate_llm_response)
        if use_rag:
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
                context_type=context_type,
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
                context_type=context_type,
            )

        # Note: Removed pre_llm_lesson_short_circuit with embedding parameter
        # Lesson handling now happens via function calling

        is_english = not user_lang or user_lang.lower() == "en"

        # Post-hook: runs trigger matching after the full text is available
        # Returns diagnostics dict with execution_result for response building
        async def _post_hook(full_response_text: str):
            from src.triggers.triggering import handle_triggers
            diagnostics = await handle_triggers(
                response=full_response_text,
                original_text=text,
                session=session,
                memory_manager=self.memory_manager,
                user_id=user_id,
            )
            return diagnostics

        def _extract_response_text(full_response_text: str) -> str:
            """Extract just the response text from potentially JSON-formatted response.
            
            Note: This is used for non-English path. For English streaming, the
            StreamingFilter in telegram_stream.py handles this during streaming.
            """
            from src.functions.intent_parser import get_intent_parser
            parser = get_intent_parser()
            parse_result = parser.parse(full_response_text)
            # Use explicit None check because empty string "" is a valid response
            # (e.g., when AI only returns function calls like send_todays_lesson)
            return parse_result.response_text if parse_result.response_text is not None else full_response_text

        if is_english:
            # Stream the LLM response directly
            # Note: Text extraction is handled by StreamingFilter in telegram_stream.py
            gen = stream_ollama(
                prompt,
                model=settings.OLLAMA_CHAT_RAG_MODEL if use_rag else None,
                language=user_lang,
            )
            
            return {"type": "stream", "generator": gen, "post_hook": _post_hook}
        else:
            # Non-English: get full LLM response first, then stream translation
            response = await self.call_ollama(
                prompt,
                model=settings.OLLAMA_CHAT_RAG_MODEL if use_rag else None,
                language=user_lang,
            )
            if response is None:
                response = "[No response from LLM]"

            # Extract just the response text before translation
            response_text = _extract_response_text(response)

            # Build translation prompt (same as translate_text but we stream it)
            translation_prompt = (
                f"Translate the following text to {user_lang}. "
                f"Return ONLY the translation, no explanations:\n\n{response_text}"
            )
            gen = stream_ollama(
                translation_prompt,
                model=None,
                language=user_lang,
            )

            # Wrap post_hook to use the original (English) response for triggers
            async def _post_hook_translated(full_translated_text: str):
                await _post_hook(response)

            return {"type": "stream", "generator": gen, "post_hook": _post_hook_translated}
