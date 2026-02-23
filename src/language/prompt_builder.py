"""
Prompt Builder: Constructs context-aware prompts from user memory, preferences, and conversation history.
Supports dynamic context assembly for Ollama LLM with token optimization.
"""

from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from src.services.timezone_utils import get_user_timezone_name, format_dt_in_timezone, to_utc
from src.models.database import MessageLog, User, Lesson
from src.memories import MemoryManager
from src.memories.constants import MemoryKey
import json


class PromptBuilder:
    """
    Assembles multi-user context-aware prompts from memories, preferences, and conversation history.
    
    Prompt Structure:
    1. System Role/Persona
    2. User Profile Context (name, preferences, goals)
    3. Relevant Memories (recent, high-confidence)
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
        "### Output Format Rules\n"
        "- The user reads replies in Telegram on a small screen.\n"
        "- Never use ASCII/Unicode tables, box-drawing tables, or markdown tables.\n"
        "- Use short paragraphs and simple bullet or numbered lists instead.\n"
        "- Keep layout plain and mobile-friendly."
    )
    
    def __init__(self, db: Session, memory_manager: Optional[MemoryManager] = None):
        self.db = db
        self.memory_manager = memory_manager or MemoryManager(db)
    
    def build_prompt(
        self,
        user_id: int,
        user_input: str,
        system_prompt: str,
        include_lesson: bool = True,
        include_conversation_history: bool = True,
        history_turns: int = 4,
        max_context_tokens: int = 2000,
        relevant_memories: Optional[List[Dict[str, Any]]] = None,
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
        if include_lesson:
            lesson_context, progress_note = self._get_today_lesson(user_id)
            if lesson_context:
                context_parts.append(f"\n### Today's ACIM Lesson\n{lesson_context}")
            if progress_note:
                context_parts.append(f"\n### Lesson Progress Note\n{progress_note}")

        # 2. User Profile Context
        profile_context = self._build_profile_context(user)
        if profile_context:
            context_parts.append(f"\n### User Profile\n{profile_context}")
        
        # 3. Goals & Learning Progress
        goals_context = self._build_goals_context(user_id)
        if goals_context:
            context_parts.append(f"\n### Current Goals\n{goals_context}")
        
        # 4. User Preferences
        prefs_context = self._build_preferences_context(user_id)
        if prefs_context:
            context_parts.append(f"\n### Preferences\n{prefs_context}")
        
        # 5. Recent Progress/Insights
        progress_context = self._build_progress_context(user_id)
        if progress_context:
            context_parts.append(f"\n### Recent Progress\n{progress_context}")

        # 5b. Semantic Relevant Memories (optional)
        semantic_context = self._build_semantic_memory_context(relevant_memories or [])
        if semantic_context:
            context_parts.append(f"\n### Relevant Memories\n{semantic_context}")
        
        # 6. Conversation History
        if include_conversation_history:
            history_context = self._build_conversation_history(user_id, history_turns)
            if history_context:
                context_parts.append(f"\n### Recent Conversation\n{history_context}")
        
        # 7. Current Message
        context_parts.append(f"\n### Current Message\nUser: {user_input}\n\nAssistant:")
        
        return "".join(context_parts)

    def build_rag_prompt(
        self,
        user_id: int,
        user_input: str,
        system_prompt: str,
        relevant_memories: Optional[List[Dict[str, Any]]] = None,
        include_conversation_history: bool = True,
        history_turns: int = 2,
        max_memories: int = 5,
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
            context_parts.append(f"\n### User\n{name}")
            local_time = self._get_user_local_time_str(user)
            if local_time:
                context_parts.append(f"\n{local_time}")
        
        # 2. Semantically relevant memories only
        semantic_context = self._build_semantic_memory_context(relevant_memories or [], max_items=max_memories)
        if semantic_context:
            context_parts.append(f"\n### Relevant Context\n{semantic_context}")
        
        # 3. Light conversation history
        if include_conversation_history:
            history_context = self._build_conversation_history(user_id, history_turns)
            if history_context:
                context_parts.append(f"\n### Recent Conversation\n{history_context}")
        
        # 4. Current message
        context_parts.append(f"\n### Current Message\nUser: {user_input}\n\nAssistant:")
        
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

        lesson_text = f"**Lesson {lesson.lesson_id}**: \"{lesson.title}\"\n\n{content}"
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

        lesson_text = f"**Lesson {lesson.lesson_id}**: \"{lesson.title}\"\n\n{content}"
        return {"lesson_text": lesson_text, "state": state}

    def _get_current_lesson_state(self, user_id: int) -> Dict[str, Any]:
        """Return current lesson state and progress note for prompt guidance.

        This implementation uses the centralized `lesson_state` helpers for
        consistent reads of `current_lesson` and `last_sent_lesson_id`.
        """
        from src.lessons.state import compute_current_lesson_state

        now = datetime.now(timezone.utc)
        day_offset = self._get_debug_day_offset(user_id)
        today = (now + timedelta(days=day_offset)).date()

        return compute_current_lesson_state(self.memory_manager, user_id, today=today)

    def _get_user_local_time_str(self, user: Any) -> Optional[str]:
        """Return a compact local time string for the user, or None if unavailable.

        Example: "Local time: 2026-02-06 18:30 (Europe/Oslo)"
        """
        try:
            # Prefer resolved timezone from helper which checks DB, memories, and language
            tz_name = None
            if self.memory_manager:
                tz_name = get_user_timezone_name(self.memory_manager, user.user_id, getattr(user, "language", None))

            if not tz_name:
                return None

            now_utc = datetime.now(timezone.utc)
            local_dt, resolved_name = format_dt_in_timezone(now_utc, tz_name)
            return f"Local time: {local_dt.strftime('%Y-%m-%d %H:%M')} ({resolved_name})"
        except Exception:
            return None

    def _get_debug_day_offset(self, user_id: int) -> int:
        """Return temporary day offset for testing (e.g., via 'next_day' command)."""
        debug_offsets = self.memory_manager.get_memory(user_id, MemoryKey.DEBUG_DAY_OFFSET)
        if not debug_offsets:
            return 0

        def _normalize_dt(value: Any) -> datetime:
            if isinstance(value, datetime):
                return to_utc(value)
            return to_utc(datetime.min)

        latest = max(debug_offsets, key=lambda x: _normalize_dt(x.get("created_at")))
        raw_value = str(latest.get("value", "")).strip()
        try:
            return int(raw_value)
        except ValueError:
            return 0

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
        """Extract user profile information from both database and stored memories."""
        parts = []
        
        # Check for stored full_name memory first, fall back to database name
        stored_name = self.memory_manager.get_memory(user.user_id, MemoryKey.FULL_NAME)
        if stored_name:
            parts.append(f"Name: {stored_name[0]['value']}")
        elif user.first_name:
            name = user.first_name
            if user.last_name:
                name += f" {user.last_name}"
            parts.append(f"Name: {name}")
        
        # Add personal background if stored
        personal_bg = self.memory_manager.get_memory(user.user_id, MemoryKey.PERSONAL_BACKGROUND)
        if personal_bg:
            parts.append(f"Background: {personal_bg[0]['value']}")
        
        if user.email:
            parts.append(f"Email: {user.email}")
        if user.phone_number:
            parts.append(f"Channel: {user.channel} ({user.phone_number})")
        else:
            parts.append(f"Channel: {user.channel}")
        if user.created_at:
            # Handle both naive and timezone-aware datetimes
            created = to_utc(user.created_at)
            days_active = (datetime.now(timezone.utc) - created).days
            parts.append(f"User since: {days_active} days ago")

        # Add user's local current date/time when available to help the assistant
        local_time = self._get_user_local_time_str(user)
        if local_time:
            parts.append(local_time)
        
        return "\n".join(parts) if parts else ""
    
    def _build_goals_context(self, user_id: int) -> str:
        """Retrieve user goals and learning objectives."""
        goals = self.memory_manager.get_memory(user_id, MemoryKey.LEARNING_GOAL)
        milestones = self.memory_manager.get_memory(user_id, MemoryKey.MILESTONE)
        
        parts = []
        if goals:
            parts.append("Learning Goals:")
            for i, g in enumerate(goals[:3], 1):  # Top 3 goals
                confidence = f" (confidence: {g['confidence']:.1%})" if g['confidence'] < 1.0 else ""
                parts.append(f"  {i}. {g['value']}{confidence}")
        
        if milestones:
            parts.append("\nCompleted Milestones:")
            for i, m in enumerate(milestones[:3], 1):  # Top 3 milestones
                parts.append(f"  {i}. {m['value']}")
        
        return "\n".join(parts) if parts else ""
    
    def _build_preferences_context(self, user_id: int) -> str:
        """Retrieve user communication and learning preferences."""
        style = self.memory_manager.get_memory(user_id, MemoryKey.LEARNING_STYLE)
        tone = self.memory_manager.get_memory(user_id, MemoryKey.PREFERRED_TONE)
        frequency = self.memory_manager.get_memory(user_id, MemoryKey.CONTACT_FREQUENCY)
        
        parts = []
        if style:
            parts.append(f"Learning Style: {style[0]['value']}")
        if tone:
            parts.append(f"Preferred Tone: {tone[0]['value']}")
        if frequency:
            parts.append(f"Contact Frequency: {frequency[0]['value']}")
        
        return "\n".join(parts) if parts else ""
    
    def _build_progress_context(self, user_id: int) -> str:
        """Retrieve recent progress and insights."""
        lessons_completed = self.memory_manager.get_memory(user_id, MemoryKey.LESSON_COMPLETED)
        insights = self.memory_manager.get_memory(user_id, MemoryKey.INSIGHT)
        
        parts = []
        if lessons_completed:
            recent = sorted(lessons_completed, key=lambda x: x['created_at'], reverse=True)[:3]
            parts.append("Recent Lessons:")
            for i, lesson in enumerate(recent, 1):
                parts.append(f"  {i}. {lesson['value']}")
        
        if insights:
            recent_insights = sorted(insights, key=lambda x: x['created_at'], reverse=True)[:2]
            parts.append("\nKey Insights:")
            for i, insight in enumerate(recent_insights, 1):
                parts.append(f"  {i}. {insight['value']}")
        
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
    
    def build_onboarding_prompt(self, system_prompt: str) -> str:
        """Build initial onboarding prompt for new users."""
        return f"""{system_prompt}

### Onboarding
You are meeting this user for the first time. Your goal is to understand:
1. Their name and preferred way to be addressed
2. Their main learning goals or interests
3. Their preferred communication style
4. How often they'd like to engage

Keep questions conversational and warm. Ask one or two questions at a time."""
