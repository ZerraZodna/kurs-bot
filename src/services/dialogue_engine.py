import logging
from typing import Dict, Any

from sqlalchemy.orm import Session

from src.config import settings
from src.core.timezone import format_dt_in_timezone, get_user_timezone_from_db
from src.language.prompt_builder import PromptBuilder
from src.lessons.delivery import _parse_lesson_int, deliver_lesson

from src.memories import MemoryManager
from src.memories.constants import MemoryCategory, MemoryKey
from src.models.database import User
from src.onboarding.flow import OnboardingFlow
from src.onboarding.service import OnboardingService
from src.scheduler import api as scheduler_api
from src.services.dialogue import (
    stream_ollama,
    get_user_language,
    translate_text,
)

logger = logging.getLogger(__name__)


class DialogueEngine:
    def __init__(self, db: Session | None = None, memory_manager: MemoryManager | None = None):
        if db is None:
            raise ValueError("DialogueEngine requires an active DB session")

        self.db = db
        self.memory_manager = memory_manager or MemoryManager(db)

        self.prompt_builder = PromptBuilder(db, self.memory_manager)
        self.onboarding = OnboardingService(db)
        self.onboarding_flow = OnboardingFlow(self.memory_manager, self.onboarding, self.call_ollama)

    @property
    def memory_judge(self):
        """Expose MemoryJudge from memory_manager for memory extraction."""
        return self.memory_manager.ai_judge

    async def call_ollama(self, prompt: str, model: str | None = None, language: str | None = None) -> str:
        """Delegate to dialogue.ollama_client with optional language hint."""
        from src.services.dialogue import call_ollama

        return await call_ollama(prompt, model, language)

    async def process_message(
        self,
        user_id: int,
        text: str,
        session: Session,
        chat_id: int | None = None,
        include_history: bool = True,
        history_turns: int = 4,
        include_lesson: bool = True,
    ) -> Dict[str, Any]:
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

        # No dual-mode; unified spiritual

        # Stage 4: Commands
        command_response = await self._handle_commands(user_id, text, session, user_lang)
        if command_response:
            return {"type": "text", "text": command_response}

        # Stage 5: Onboarding
        onboarding_response = await self._handle_onboarding_stage(user_id, text, session)
        if onboarding_response:
            return {"type": "text", "text": onboarding_response}

        # Stage 6: Lessons & Schedule
        lesson_response = await self._handle_lesson_and_schedule_stage(
            user_id, text, session, user_lang, include_lesson
        )
        if lesson_response:
            return {"type": "text", "text": lesson_response}

        # FALLBACK TO LLM STREAMING (ALWAYS)
        return await self._generate_streaming_response(
            user_id,
            text,
            session,
            user_lang,
            include_history,
            history_turns,
            include_lesson,
            context_aware_turns=True,
        )

    async def _detect_and_store_language(self, user_id: int, text: str) -> str:
        from src.services.dialogue import detect_and_store_language

        return await detect_and_store_language(self.memory_manager, user_id, text)

    async def _check_user_restrictions(self, user_id: int, text: str, user: User, session: Session) -> str | None:
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

    async def _handle_commands(self, user_id: int, text: str, session: Session, user_lang: str) -> str | None:
        """Handle various specialized commands."""
        from src.services.dialogue import handle_list_memories, handle_custom_system_prompt_command

        list_memories = handle_list_memories(text, self.memory_manager, session, user_id)
        if list_memories:
            return list_memories

        prompt_cmd_response = handle_custom_system_prompt_command(text, self.memory_manager, user_id)
        if prompt_cmd_response:
            return prompt_cmd_response

        # /help command
        if text.strip().lower() in ["/help", "/start"]:
            help_text = """<b>🌟 Kurs Bot - ACIM Spiritual Companion</b>

<b>📖 Lessons & Reminders</b>
• Daily ACIM lessons sent automatically
• <b>Set your time:</b> "Set daily lesson reminder for 9AM" or "morning"
• <b>Manual:</b> <code>/lesson 29</code>, "Next lesson", "Repeat lesson"
• "What's my current lesson?"

<b>🧠 Personal Memory</b>
• I remember our conversations & preferences
• "Forget [topic]" to remove specific memory
• "Remember [important fact]" for persistence
• "List my memories" (existing command)

<b>⚙️ Personalization</b>
• Language auto-detected (EN/DE/others)
• Custom system prompt: [use existing command]
• Timezone auto-detected from messages

<b>🔒 Privacy/GDPR</b>
• /delete - full data deletion
• /consent - manage data permissions
• Data retention: 90 days conversations, profiles forever until deleted

<b>Talk naturally! 🙏</b>
Type /help anytime.

/start also shows this help."""
            if user_lang and user_lang.lower() not in ("en",):
                help_text = await translate_text(help_text, user_lang, self.call_ollama)
            return help_text

        # /lesson command
        if text.strip().startswith("/lesson"):
            parts = text.strip().split(maxsplit=1)
            target_lesson_id = _parse_lesson_int(parts[1] if len(parts) > 1 else None)
            message = deliver_lesson(session, user_id, target_lesson_id, self.memory_manager, user_lang)
            if message:
                logger.info(f"[command /lesson user={user_id}] lesson_id={target_lesson_id or 'current'}")
                return message
            else:
                return "Sorry, could not deliver lesson. Please check lesson number or try /help."

        return None

    async def _handle_onboarding_stage(self, user_id: int, text: str, session: Session) -> str | None:
        """Handle onboarding flow."""
        if self.onboarding_flow and self.onboarding.should_show_onboarding(user_id):
            onboarding_response = await self.onboarding_flow.handle_onboarding(user_id, text, session)
            return onboarding_response

        return None

    async def _handle_lesson_and_schedule_stage(
        self, user_id: int, text: str, session: Session, user_lang: str, include_lesson: bool
    ) -> str | None:
        from src.services.dialogue import handle_schedule_messages

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

        return None

    async def _generate_streaming_response(
        self,
        user_id: int,
        text: str,
        session: Session,
        user_lang: str,
        include_history: bool,
        history_turns: int,
        include_lesson: bool,
        context_aware_turns: bool = True,
    ) -> Dict[str, Any]:
        """Unified streaming response generator (English/non-English)."""
        relevant_memories = await self._get_relevant_memories(user_id, text, session)
        context_type = self._detect_context_type(user_id, text)

        # Build spiritual prompt (ALWAYS) - check for custom override via memories
        custom_prompt_mem = self.memory_manager.get_memory(user_id, MemoryKey.CUSTOM_SYSTEM_PROMPT)
        selected_key_mem = self.memory_manager.get_memory(user_id, MemoryKey.SELECTED_SYSTEM_PROMPT_KEY)
        system_prompt = settings.SYSTEM_PROMPT  # default spiritual

        if custom_prompt_mem and custom_prompt_mem[0].get("value"):
            system_prompt = str(custom_prompt_mem[0].get("value"))
        elif selected_key_mem and selected_key_mem[0].get("value"):
            # Load from PromptTemplate DB (simple version since registry removed)
            from src.models.templates import PromptTemplate

            pt = (
                session
                .query(PromptTemplate)
                .filter(PromptTemplate.key == str(selected_key_mem[0].get("value")))
                .first()
            )
            if pt:
                system_prompt = pt.text

        prompt = self.prompt_builder.build_prompt(
            user_id=user_id,
            user_input=text,
            system_prompt=system_prompt,
            include_lesson=include_lesson,
            include_conversation_history=include_history,
            history_turns=history_turns,
            max_age_hours=24.0,
            relevant_memories=relevant_memories,
            context_type=context_type,
        )

        # Common streaming logic
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

    async def _get_relevant_memories(self, user_id: int, text: str, session: Session) -> list:
        """Retrieve ALL active non-expired memories (full context)."""
        from src.memories.memory_handler import MemoryHandler
        from src.core.timezone import utc_now

        handler = MemoryHandler(session)
        now = utc_now()
        all_memories = handler.list_active_memories(user_id=user_id)
        valid_memories = [m for m in all_memories if not handler._is_expired(m.ttl_expires_at, now)]
        relevant_memories = [
            {"memory_id": m.memory_id, "key": m.key, "value": m.value, "category": m.category, "similarity": 1.0}
            for m in sorted(valid_memories, key=lambda m: m.updated_at or m.created_at, reverse=True)
        ]
        return relevant_memories

    def _detect_context_type(self, user_id: int, text: str) -> str:
        """Detect conversation context type for function availability."""

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

    async def _handle_schedule_request(self, user_id: int, text: str, session: Session) -> str | None:
        """Handle explicit schedule requests (unchanged helper)."""
        from src.scheduler.schedule_query_handler import build_schedule_status_response
        from src.services.dialogue import translate_text

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
