"""
Prompt Builder: Constructs context-aware prompts from user memory, preferences, and conversation history.
Supports dynamic context assembly for Ollama LLM with token optimization.
"""

from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
import re
from src.core.timezone import get_user_timezone_from_db, format_dt_in_timezone, to_utc
from src.models.database import MessageLog, User, Lesson
from src.memories import MemoryManager
from src.memories.constants import MemoryKey
from src.memories.topics import MemoryTopic
from src.functions.definitions import FunctionDefinitions, get_function_definitions
import json


class PromptBuilder:
    """
    Assembles multi-user context-aware prompts from memories, preferences, and conversation history.
    
    Prompt Structure:
    1. System Role/Persona
    2. User Profile Context (name, preferences, goals)
    3. Relevant Memories (recent)
    4. Conversation History (recent turns)
    5. Current User Input
    """
    
    # Memory category priority for context inclusion (0=highest priority)
    MEMORY_PRIORITY = {
        "profile": 0,
        "goals": 1,
        "preferences": 2,
        "progress": 3,
        "insights": 4,
        "conversation": 5,
    }
    
    # Max tokens to reserve for each context section (approximate)
    TOKEN_LIMITS = {
        "profile": 150,
        "goals": 200,
        "preferences": 100,
        "progress": 150,
        "conversation_history": 400,
    }

    TELEGRAM_OUTPUT_RULES = (
        "== Output Format Rules ==\n"
        "- The user reads replies in Telegram on a small screen.\n"
        "- Never use ASCII/Unicode tables, box-drawing tables, or markdown tables.\n"
        "- Use <b> for bold text instead of ** or __\n"
        "- Use <i> for italic text instead of * or _\n"
        "- Use <pre> for code blocks or formatted content instead of ```\n"
        "- Use short paragraphs and simple bullet or numbered lists instead.\n"
        "- Keep layout plain and mobile-friendly."
    )

    LESSON_TEXT_RETRIEVAL_RULES = (
        "== Lesson Text Retrieval Rules ==\n"
        "- If the user asks for today's lesson or a specific lesson number/text, return the lesson text exactly as provided.\n"
        "- Do not summarize, interpret, explain, or rewrite the lesson text.\n"
        "- Return only the lesson body."
    )
    
    def __init__(self, db: Session, memory_manager: Optional[MemoryManager] = None):
        self.db = db
        self.memory_manager = memory_manager or MemoryManager(db)
        self.function_definitions = get_function_definitions()
    
    def build_prompt(
        self,
        user_id: int,
        user_input: str,
        system_prompt: str,
        include_lesson: bool = True,
        include_conversation_history: bool = True,
        history_turns: int = 4,
        relevant_memories: Optional[List[Dict[str, Any]]] = None,
        context_type: str = "general_chat",
        include_functions: bool = True,
    ) -> str:
        """
        Build a context-rich prompt for the LLM.
        
        Args:
            user_id: User ID from database
            user_input: Current user message
            system_prompt: Base system/persona prompt
            include_lesson: Include today's ACIM lesson in context
            include_conversation_history: Include recent conversation context
            history_turns: Number of recent message pairs to include
            max_context_tokens: Soft limit on context section size (approximate)
        
        Returns:
            Formatted prompt ready for Ollama
        """
        # Fetch user details
        user = self.db.query(User).filter_by(user_id=user_id).first()
        if not user:
            # Fallback for unknown users
            return f"{system_prompt}\n\nUser: {user_input}\n\nAssistant:"
        
        # Build context blocks
        context_parts = [system_prompt]
        output_rules = self._build_channel_output_rules(user)
        if output_rules:
            context_parts.append(f"\n\n{output_rules}")
        
        # 1. Today's Lesson (optional)
        # Skip injecting lesson into prompt when user explicitly asks for it -
        # let the function calling system (send_todays_lesson) provide the full text instead.
        is_direct_lesson_request = self._is_direct_lesson_text_request(user_input)
        if include_lesson and not is_direct_lesson_request:
            lesson_context, progress_note = self._get_today_lesson(user_id)
            if lesson_context:
                context_parts.append(f"\n== Today's ACIM Lesson\n{lesson_context}")
            if progress_note:
                context_parts.append(f"\n== Lesson Progress Note\n{progress_note}")
        elif is_direct_lesson_request:
            # Add instruction to use function instead of summarizing
            context_parts.append(
                f"\n-- Lesson Text Request\n"
                f"The user is asking for the lesson text. "
                f"DO NOT summarize or describe the lesson. "
                f"Instead, call the send_todays_lesson function to return the full lesson text."
            )

        # 2. User Profile Context
        profile_context = self._build_profile_context(user)
        if profile_context:
            context_parts.append(f"\n-- User Profile\n{profile_context}")
                
        # 4. User Preferences
        prefs_context = self._build_preferences_context(user_id)
        if prefs_context:
            context_parts.append(f"\n-- Preferences\n{prefs_context}")
        
        # 5. Semantic Relevant Memories (optional)
        semantic_context = self._build_semantic_memory_context(relevant_memories or [])
        if semantic_context:
            context_parts.append(f"\n-- Relevant Memories\n{semantic_context}")
        
        # 6. Conversation History
        if include_conversation_history:
            history_context = self._build_conversation_history(user_id, history_turns)
            if history_context:
                context_parts.append(f"\n-- Recent Conversation\n{history_context}")
        
        # 7. Function Definitions (if enabled)
        if include_functions:
            function_context = self._build_function_context(context_type)
            if function_context:
                context_parts.append(f"\n\n{function_context}")
        
        # 8. Onboarding Next Step Context (if in onboarding)
        if context_type.startswith("onboarding"):
            onboarding_context = self._build_onboarding_next_step_context(user_id)
            if onboarding_context:
                context_parts.append(onboarding_context)
        
        # 9. Current Message
        context_parts.append(f"\n-- Current Message\nUser: {user_input}\n\nAssistant:")
        
        return "".join(context_parts)

    def _is_direct_lesson_text_request(self, user_input: str) -> bool:
        """Detect direct requests for today's lesson or specific lesson text."""
        raw = (user_input or "").lower()
        if not raw:
            return False

        normalized = re.sub(r"[^\w\s]", " ", raw)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        tokens = set(normalized.split())

        lesson_words = {"lesson", "leksjon", "lekse"}
        has_lesson_word = bool(tokens & lesson_words)
        if not has_lesson_word:
            return False

        if re.search(
            r"\b(?:lesson|leksjon|lekse)\s*(?:number|nr|no|text|tekst|content|innhold)?\s*#?\s*\d{1,3}\b",
            normalized,
        ):
            return True

        if re.search(r'\\btoday\\b.*?(?:lesson|leksjon)|lesson\\s+for\\s+today|today\'?s?\\s+lesson', normalized, re.I):
            return True
        today_words = {"today", "todays", "idag", "dagens"}
        has_today_word = bool(tokens & today_words) or ("i dag" in normalized)
        return has_today_word

    def build_rag_prompt(
        self,
        user_id: int,
        user_input: str,
        system_prompt: str,
        relevant_memories: Optional[List[Dict[str, Any]]] = None,
        include_conversation_history: bool = True,
        history_turns: int = 2,
        max_memories: int = 5,
        context_type: str = "general_chat",
        include_functions: bool = True,
    ) -> str:
        """
        Build a RAG-focused prompt with minimal context.
        
        Skips ACIM lesson and category-based memories.
        Uses only semantically relevant memories from the search.
        
        Args:
            user_id: User ID from database
            user_input: Current user message
            system_prompt: Base system/persona prompt
            relevant_memories: Semantically matched memories from search
            include_conversation_history: Include recent conversation context
            history_turns: Number of recent message pairs to include
            max_memories: Maximum relevant memories to include
        
        Returns:
            Formatted RAG prompt ready for Ollama
        """
        # Fetch user details for minimal profile info only
        user = self.db.query(User).filter_by(user_id=user_id).first()
        if not user:
            return f"{system_prompt}\n\nUser: {user_input}\n\nAssistant:"
        
        context_parts = [system_prompt]
        output_rules = self._build_channel_output_rules(user)
        if output_rules:
            context_parts.append(f"\n\n{output_rules}")
        
        # 1. Minimal user profile (just name if available)
        if user.first_name:
            name = user.first_name
            if user.last_name:
                name += f" {user.last_name}"
            context_parts.append(f"\n-- User\n{name}")
            local_time = self._get_user_local_time_str(user)
            if local_time:
                context_parts.append(f"\n{local_time}")
        
        # 2. Semantically relevant memories only
        semantic_context = self._build_semantic_memory_context(relevant_memories or [], max_items=max_memories)
        if semantic_context:
            context_parts.append(f"\n-- Relevant Context\n{semantic_context}")
        
        # 3. Light conversation history
        if include_conversation_history:
            history_context = self._build_conversation_history(user_id, history_turns)
            if history_context:
                context_parts.append(f"\n-- Recent Conversation\n{history_context}")
        
        # 4. Function Definitions (if enabled)
        if include_functions:
            function_context = self._build_function_context(context_type)
            if function_context:
                context_parts.append(f"\n\n{function_context}")
        
        # 5. Onboarding Next Step Context (if in onboarding)
        if context_type.startswith("onboarding"):
            onboarding_context = self._build_onboarding_next_step_context(user_id)
            if onboarding_context:
                context_parts.append(onboarding_context)
        
        # 6. Current message
        context_parts.append(f"\n-- Current Message\nUser: {user_input}\n\nAssistant:")
        
        return "".join(context_parts)

    def _build_channel_output_rules(self, user: Any) -> str:
        """Return channel-specific output formatting constraints."""
        channel = (getattr(user, "channel", "") or "").strip().lower()
        if channel == "telegram":
            return self.TELEGRAM_OUTPUT_RULES
        return ""

    def _build_semantic_memory_context(
        self,
        memories: List[Dict[str, Any]],
        max_items: int = 5,
        max_value_chars: int = 200,
    ) -> str:
        """Build a compact block of semantically relevant memories."""
        if not memories:
            return ""

        lines: List[str] = []
        for memory in memories[:max_items]:
            value = str(memory.get("value", "")).strip()
            if not value:
                continue
            if len(value) > max_value_chars:
                value = value[:max_value_chars].rsplit(" ", 1)[0] + "..."

            key = str(memory.get("key", "memory")).strip()
            category = str(memory.get("category", "")).strip()
            label = key if key else "memory"
            if category:
                label = f"{label} ({category})"

            lines.append(f"- {label}: {value}")

        return "\n".join(lines)

    def _get_today_lesson(self, user_id: int, max_chars: int = 800) -> Tuple[str, Optional[str]]:
        """Return today's lesson text based on user progress.

        Defaults to Lesson 1 unless the user is explicitly on another lesson.
        """
        state = self._get_current_lesson_state(user_id)
        lesson_id = state.get("lesson_id")
        if not lesson_id:
            return "", None

        lesson = self.db.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
        if not lesson:
            return "", None

        content = lesson.content or ""
        if max_chars and len(content) > max_chars:
            content = content[:max_chars].rsplit(" ", 1)[0] + "..."

        lesson_text = f"<b>Lesson {lesson.lesson_id}</b>: \"{lesson.title}\"\n\n{content}"
        return lesson_text, state.get("progress_note")

    def get_today_lesson_context(self, user_id: int, max_chars: int = 800) -> Dict[str, Any]:
        """Return lesson text and state for deterministic responses."""
        state = self._get_current_lesson_state(user_id)
        lesson_id = state.get("lesson_id")
        if not lesson_id:
            return {"lesson_text": "", "state": state}

        lesson = self.db.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
        if not lesson:
            return {"lesson_text": "", "state": state}

        content = lesson.content or ""
        if max_chars and len(content) > max_chars:
            content = content[:max_chars].rsplit(" ", 1)[0] + "..."
        
        lesson_text = f"<b>Lesson {lesson.lesson_id}</b>: \"{lesson.title}\"\n\n{content}"
        return {"lesson_text": lesson_text, "state": state}

    def _get_current_lesson_state(self, user_id: int) -> Dict[str, Any]:
        """Return current lesson state and progress note for prompt guidance.

        This implementation uses the centralized `lesson_state` helpers for
        consistent reads of `current_lesson` and `last_sent_lesson_id`.
        """
        from src.lessons.state import compute_current_lesson_state

        now = datetime.now(timezone.utc)

        return compute_current_lesson_state(self.memory_manager, user_id, today=now)

    def _get_user_local_time_str(self, user: Any) -> Optional[str]:
        """Return a compact local time string for the user, or None if unavailable.

        Example: "Local time: 2026-02-06 18:30 (Europe/Oslo)"
        """
        try:
            # Prefer resolved timezone from helper which checks DB, memories, and language
            tz_name = None
            if self.memory_manager:
                tz_name = get_user_timezone_from_db(self.db.object_session, user.user_id)

            if not tz_name:
                return None

            now_utc = datetime.now(timezone.utc)
            local_dt, resolved_name = format_dt_in_timezone(now_utc, tz_name)
            return f"Local time: {local_dt.strftime('%Y-%m-%d %H:%M')} ({resolved_name})"
        except Exception:
            return None

    def _get_last_lesson_from_logs(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Fallback: infer last sent lesson from message logs."""
        messages = (
            self.db.query(MessageLog)
            .filter(MessageLog.user_id == user_id, MessageLog.direction == "outbound")
            .order_by(MessageLog.created_at.desc())
            .limit(20)
            .all()
        )
        if not messages:
            return None

        import re

        for msg in messages:
            content = msg.content or ""
            match = re.search(r"\bLesson\s+(\d+)\b", content)
            if match:
                return {"lesson_id": int(match.group(1)), "created_at": msg.created_at}

        return None

    def _parse_lesson_id(self, value: str) -> Optional[int]:
        """Parse lesson id from memory value (e.g., '1' or 'Lesson 1')."""
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            digits = "".join(ch for ch in value if ch.isdigit())
            return int(digits) if digits else None
    
    def _build_profile_context(self, user: Any) -> str:
        """Extract user profile information from topic-based memories."""
        # Get consolidated profile from topic manager
        profile = self.memory_manager.topic_manager.get_profile_context(user.user_id, user)
        
        # Format as prompt lines
        parts = []
        for field_name, value in profile.items():
            parts.append(f"{field_name.replace('_', ' ').title()}: {value}")
        
        # Add channel info
        if user.phone_number:
            parts.append(f"Channel: {user.channel} ({user.phone_number})")
        else:
            parts.append(f"Channel: {user.channel}")
        
        # Add user tenure
        if user.created_at:
            created = to_utc(user.created_at)
            days_active = (datetime.now(timezone.utc) - created).days
            parts.append(f"User since: {days_active} days ago")
        
        # Add local time
        local_time = self._get_user_local_time_str(user)
        if local_time:
            parts.append(local_time)
                
        return "\n".join(parts) if parts else ""
        
    def _build_preferences_context(self, user_id: int) -> str:
        """Retrieve user communication and learning preferences."""
        tone = self.memory_manager.get_memory(user_id, MemoryKey.PREFERRED_TONE)
        
        parts = []
        if tone:
            parts.append(f"Preferred Tone: {tone[0]['value']}")
        
        return "\n".join(parts) if parts else ""
        
    def _build_conversation_history(self, user_id: int, num_turns: int = 4) -> str:
        """Retrieve recent conversation history for multi-turn context."""
        # Query recent messages for this user, ordered by creation date
        messages = self.db.query(MessageLog).filter(
            MessageLog.user_id == user_id,
            MessageLog.status.in_(["delivered", "sent"]),  # Only successful messages
        ).order_by(MessageLog.created_at.desc()).limit(num_turns * 2).all()
        
        if not messages:
            return ""
        
        # Reverse to chronological order (oldest first)
        messages = list(reversed(messages))
        
        parts = []
        # Take last N turns (each turn = 2 messages: user + assistant)
        for msg in messages[-(num_turns * 2):]:
            if msg.direction == "inbound":
                parts.append(f"User: {msg.content}")
            else:
                parts.append(f"Assistant: {msg.content}")
        
        return "\n".join(parts) if parts else ""
    
    def _build_function_context(self, context_type: str) -> str:
        """Build function definitions context for the given context type."""
        return self.function_definitions.for_context(context_type)
    
    def _build_onboarding_next_step_context(self, user_id: int) -> str:
        """Build context for the next onboarding step to guide the AI.
        
        This injects the next onboarding question into the prompt so the AI
        knows what to ask after extracting information like the user's name.
        """
        from src.onboarding.service import OnboardingService
        
        onboarding = OnboardingService(self.db)
        status = onboarding.get_onboarding_status(user_id)
        
        # If onboarding is complete, no need to add context
        if status.get("onboarding_complete"):
            return ""
        
        # Get the next onboarding prompt
        next_prompt = onboarding.get_onboarding_prompt(user_id)
        if not next_prompt:
            return ""
        
        # Determine which step is next based on status
        next_step = status.get("next_step", "unknown")
        
        return f"""
-- Next Onboarding Step
Current step: {next_step}

After acknowledging the user's input, ask this next question:
"{next_prompt}"

Important: Combine your acknowledgment with the next question naturally. For example:
- "Nice to meet you, Johannes! What would you like to talk about today?" → WRONG
- "Nice to meet you, Johannes! To help me serve you better, could you tell me if you're comfortable with me storing our conversation to personalize your experience?" → CORRECT

Always transition smoothly to the next onboarding question."""
    
    def _detect_onboarding_stage(self, user_id: int) -> Optional[str]:
        """Detect specific onboarding stage from pending step memory."""
        from src.memories.constants import MemoryKey
        from src.functions.definitions import FunctionDefinitions
        
        pending_step = self.memory_manager.get_memory(user_id, MemoryKey.ONBOARDING_STEP_PENDING)
        if not pending_step:
            return None
        
        # Get the step value from the most recent memory
        step_value = str(pending_step[0].get("value", "")).lower()
        
        # Use centralized stage map from FunctionDefinitions (DRY)
        return FunctionDefinitions.ONBOARDING_STAGE_MAP.get(step_value)
    
    def _detect_context_from_state(self, user_id: int) -> str:
        """Detect context based on user state."""
        # Check for pending schedule request
        from src.memories.constants import MemoryKey
        from src.memories.topics import MemoryTopic
        pending_schedule = self.memory_manager.get_memory(user_id, MemoryKey.SCHEDULE_REQUEST_PENDING)
        if pending_schedule:
            return "schedule_setup"
        
        # Check for specific onboarding stage first
        onboarding_stage = self._detect_onboarding_stage(user_id)
        if onboarding_stage:
            return onboarding_stage
        
        # Check if user is new (general onboarding)
        user = self.db.query(User).filter_by(user_id=user_id).first()
        if user and (datetime.now(timezone.utc) - to_utc(user.created_at)).days < 1:
            return "onboarding"
        
        # Check for morning lesson confirmation
        from src.lessons.state import compute_current_lesson_state
        state = compute_current_lesson_state(self.memory_manager, user_id)
        if state.get("needs_confirmation"):
            return "morning_lesson_confirmation"
        
        return "general_chat"
                
    def build_onboarding_prompt(self, system_prompt: str) -> str:
        """Build initial onboarding prompt for new users."""
        return f"""{system_prompt}

-- Onboarding
You are meeting this user for the first time. Your goal is to understand:
1. Their name and preferred way to be addressed
2. Their main learning goals or interests
3. Their preferred communication style
4. How often they'd like to engage

Keep questions conversational and warm. Ask one or two questions at a time."""
