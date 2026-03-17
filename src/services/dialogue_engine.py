import logging
from typing import Dict, Optional

from sqlalchemy.orm import Session

from src.config import settings
from src.core.timezone import format_dt_in_timezone, get_user_timezone_from_db
from src.language.prompt_builder import PromptBuilder
from src.language.prompt_registry import get_prompt_registry
from src.memories import MemoryManager
from src.memories.constants import MemoryCategory, MemoryKey
from src.memories.semantic_search import get_semantic_search_service
from src.models.database import User
from src.onboarding.flow import OnboardingFlow
from src.onboarding.service import OnboardingService
from src.scheduler import api as scheduler_api
from src.services.dialogue import (
    stream_ollama,
)

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
        from src.services.dialogue import call_ollama

        return await call_ollama(prompt, model, language)

    async def process_message(
        self,
        user_id: int,
        text: str,
        session: Session,
        chat_id: Optional[int] = None,
        include_history: bool = True,
        history_turns: int = 4,
        include_lesson: bool = True,
    ) -> Dict[str, any]:
        """
        Unified message processing - ALWAYS returns streaming-ready response.

        Returns dict:
        - {"type": "text", "text": str} for early responses (commands, onboarding, etc.)
        - {"type": "stream", "generator": AsyncIterator[str], "post_hook": callable} for LLM

        chat_id optional for Telegram-specific context if needed.
        """
        user = session.query(User).filter_by(user_id=user_id).first()
        if not user:
            return {"type": "text", "text": "User not found."}

        # SHARED 5-STAGE PIPELINE (extracted from both old methods)
        # Stage 1: Restrictions & GDPR
        restriction_response = await self._check_user_restrictions(user_id, text, user, session)
        if restriction_response:
            return {"type": "text", "text": restriction_response}

        # Stage 2: Language detection
        user_lang = await self._detect_and_store_language(user_id, text)

        # Stage 3: RAG setup
        text, use_rag, rag_response = self._setup_rag_configuration(user_id, text)
        if rag_response:
            return {"type": "text", "text": rag_response}

        # Stage 4: Commands
        command_response = await self._handle_commands(user_id, text, session, use_rag)
        if command_response:
            return {"type": "text", "text": command_response}

        # Stage 5: Onboarding
        onboarding_response = await self._handle_onboarding_stage(user_id, text, session, use_rag)
        if onboarding_response:
            return {"type": "text", "text": onboarding_response}

        # Stage 6: Lessons & Schedule
        lesson_response = await self._handle_lesson_and_schedule_stage(
            user_id, text, session, user_lang, include_lesson, use_rag
        )
        if lesson_response:
            return {"type": "text", "text": lesson_response}

        # FALLBACK TO LLM STREAMING (ALWAYS)
        return await self._generate_streaming_response(
            user_id, text, session, user_lang, use_rag, include_history, history_turns, include_lesson
        )

    async def _detect_and_store_language(self, user_id: int, text: str) -> str:
        from src.services.dialogue import detect_and_store_language

        return await detect_and_store_language(self.memory_manager, user_id, text)

    async def _check_user_restrictions(self, user_id: int, text: str, user: User, session: Session) -> Optional[str]:
        """Handle GDPR commands and check if user is deleted or restricted."""
        from src.services.dialogue import handle_gdpr_commands

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
        from src.services.dialogue import parse_rag_prefix

        text, use_rag = parse_rag_prefix(text)

        return text, use_rag, None

    async def _handle_commands(self, user_id: int, text: str, session: Session, use_rag: bool) -> Optional[str]:
        """Handle various specialized commands."""
        from src.services.dialogue import handle_list_memories, handle_rag_prompt_command

        if use_rag:
            list_memories = handle_list_memories(text, self.memory_manager, session, user_id)
            if list_memories:
                return list_memories

            prompt_cmd_response = handle_rag_prompt_command(text, self.memory_manager, user_id)
            if prompt_cmd_response:
                return prompt_cmd_response

        return None

    async def _handle_onboarding_stage(self, user_id: int, text: str, session: Session, use_rag: bool) -> Optional[str]:
        """Handle onboarding flow."""
        if self.onboarding_flow and self.onboarding.should_show_onboarding(user_id) and not use_rag:
            # from src.memories.constants import MemoryKey
            # pending_step = self.memory_manager.get_memory(user_id, MemoryKey.ONBOARDING_STEP_PENDING)
            onboarding_response = await self.onboarding_flow.handle_onboarding(user_id, text, session)
            return onboarding_response

        return None

    async def _handle_lesson_and_schedule_stage(
        self, user_id: int, text: str, session: Session, user_lang: str, include_lesson: bool, use_rag: bool
    ) -> Optional[str]:
        from src.services.dialogue import handle_schedule_messages, maybe_send_next_lesson

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

    async def _generate_streaming_response(
        self,
        user_id: int,
        text: str,
        session: Session,
        user_lang: str,
        use_rag: bool,
        include_history: bool,
        history_turns: int,
        include_lesson: bool,
    ) -> Dict[str, any]:
        """Unified streaming response generator (English/non-English)."""
        relevant_memories = await self._get_relevant_memories(user_id, text, session)
        context_type = self._detect_context_type(user_id, text, use_rag)

        # Build prompt
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

        is_english = not user_lang or user_lang.lower() == "en"

        async def post_hook(full_response_text: str):
            from src.functions import get_function_executor, get_intent_parser

            parser = get_intent_parser()
            parse_result = parser.parse(full_response_text)
            diagnostics = {}
            if parse_result.response_text:
                diagnostics["response_text"] = parse_result.response_text
            if parse_result.functions:
                executor = get_function_executor()
                execution_context = {
                    "user_id": user_id,
                    "session": session,
                    "memory_manager": self.memory_manager,
                    "original_text": text,
                }
                execution_result = await executor.execute_all(
                    parse_result.functions, execution_context, continue_on_error=True
                )
                diagnostics["execution_result"] = execution_result
                diagnostics["dispatched_actions"] = [r.function_name for r in execution_result.results if r.success]
            return diagnostics

        def extract_response_text(full_response_text: str) -> str:
            from src.functions.intent_parser import get_intent_parser

            parser = get_intent_parser()
            parse_result = parser.parse(full_response_text)
            return parse_result.response_text if parse_result.response_text is not None else full_response_text

        if is_english:
            gen = stream_ollama(
                prompt,
                model=None,
                language=user_lang,
            )
            return {"type": "stream", "generator": gen, "post_hook": post_hook}
        else:
            response = await self.call_ollama(prompt, None, user_lang)
            if response is None:
                response = "[No response from LLM]"
            response_text = extract_response_text(response)

            translation_prompt = f"Translate to {user_lang}. Return ONLY translation:\n\n{response_text}"
            gen = stream_ollama(translation_prompt, None, user_lang)

            async def post_hook_translated(full_translated: str):
                await post_hook(response)

            return {"type": "stream", "generator": gen, "post_hook": post_hook_translated}

    def _detect_context_type(self, user_id: int, text: str, use_rag: bool) -> str:
        """Detect conversation context type for function availability."""
        if use_rag:
            return "rag"

        from src.functions.definitions import FunctionDefinitions
        from src.memories.constants import MemoryKey

        pending_step = self.memory_manager.get_memory(user_id, MemoryKey.ONBOARDING_STEP_PENDING)
        if pending_step:
            step_value = str(pending_step[0].get("value", "")).lower()
            if step_value in FunctionDefinitions.ONBOARDING_STAGE_MAP:
                return FunctionDefinitions.ONBOARDING_STAGE_MAP[step_value]

        if self.onboarding and self.onboarding.should_show_onboarding(user_id):
            return "onboarding"

        schedule_keywords = ["schedule", "reminder", "time", "daily", "lesson time"]
        if any(kw in text.lower() for kw in schedule_keywords):
            return "schedule_setup"

        return "general_chat"

    async def _get_relevant_memories(self, user_id: int, text: str, session: Session) -> list:
        """Retrieve relevant memories."""
        relevant_memories = []
        search_service = get_semantic_search_service()
        results = await search_service.search_memories(user_id=user_id, query_text=text, session=session)
        relevant_memories = [
            {"memory_id": m.memory_id, "key": m.key, "value": m.value, "category": m.category, "similarity": s}
            for m, s in results
        ]
        return relevant_memories

    async def _handle_schedule_request(self, user_id: int, text: str, session: Session) -> Optional[str]:
        """Handle explicit schedule requests (unchanged helper)."""
        from src.scheduler.schedule_query_handler import build_schedule_status_response
        from src.services.dialogue import get_user_language, translate_text

        schedules = scheduler_api.get_user_schedules(user_id, session=session)
        if schedules:
            tz_name = get_user_timezone_from_db(self.db.object_session, user_id)
            resp_text = build_schedule_status_response(schedules, tz_name)
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

        time_memories = self.memory_manager.get_memory(user_id, MemoryKey.PREFERRED_LESSON_TIME)
        if not time_memories:
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

        time_str = time_memories[0]["value"]
        try:
            schedule = scheduler_api.create_daily_schedule(
                user_id=user_id, lesson_id=None, time_str=time_str, session=session
            )
            tz_name = get_user_timezone_from_db(self.db.object_session, user_id)
            time_display = (
                f"{format_dt_in_timezone(schedule.next_send_time, tz_name)[0]:%H:%M}"
                if schedule.next_send_time
                else f"{scheduler_api.parse_time_string(time_str)[0]:02d}:{scheduler_api.parse_time_string(time_str)[1]:02d}"
            )

            name_memories = self.memory_manager.get_memory(user_id, MemoryKey.FIRST_NAME)
            name = name_memories[0]["value"] if name_memories else "friend"

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
        """Return onboarding prompt sequence for new users."""
        return self.prompt_builder.build_onboarding_prompt(settings.SYSTEM_PROMPT)
