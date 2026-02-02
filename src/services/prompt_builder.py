"""
Prompt Builder: Constructs context-aware prompts from user memory, preferences, and conversation history.
Supports dynamic context assembly for Ollama LLM with token optimization.
"""

from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from src.models.database import Memory, MessageLog, User
from src.services.memory_manager import MemoryManager
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
    
    def __init__(self, db: Session, memory_manager: Optional[MemoryManager] = None):
        self.db = db
        self.memory_manager = memory_manager or MemoryManager(db)
    
    def build_prompt(
        self,
        user_id: int,
        user_input: str,
        system_prompt: str,
        include_conversation_history: bool = True,
        history_turns: int = 4,
        max_context_tokens: int = 2000,
    ) -> str:
        """
        Build a context-rich prompt for the LLM.
        
        Args:
            user_id: User ID from database
            user_input: Current user message
            system_prompt: Base system/persona prompt
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
        
        # 1. User Profile Context
        profile_context = self._build_profile_context(user)
        if profile_context:
            context_parts.append(f"\n### User Profile\n{profile_context}")
        
        # 2. Goals & Learning Progress
        goals_context = self._build_goals_context(user_id)
        if goals_context:
            context_parts.append(f"\n### Current Goals\n{goals_context}")
        
        # 3. User Preferences
        prefs_context = self._build_preferences_context(user_id)
        if prefs_context:
            context_parts.append(f"\n### Preferences\n{prefs_context}")
        
        # 4. Recent Progress/Insights
        progress_context = self._build_progress_context(user_id)
        if progress_context:
            context_parts.append(f"\n### Recent Progress\n{progress_context}")
        
        # 5. Conversation History
        if include_conversation_history:
            history_context = self._build_conversation_history(user_id, history_turns)
            if history_context:
                context_parts.append(f"\n### Recent Conversation\n{history_context}")
        
        # 6. Current Message
        context_parts.append(f"\n### Current Message\nUser: {user_input}\n\nAssistant:")
        
        return "".join(context_parts)
    
    def _build_profile_context(self, user: Any) -> str:
        """Extract user profile information."""
        parts = []
        if user.first_name:
            parts.append(f"Name: {user.first_name}")
            if user.last_name:
                parts.append(f" {user.last_name}")
        if user.email:
            parts.append(f"Email: {user.email}")
        if user.phone_number:
            parts.append(f"Channel: {user.channel} ({user.phone_number})")
        else:
            parts.append(f"Channel: {user.channel}")
        if user.created_at:
            # Handle both naive and timezone-aware datetimes
            created = user.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            days_active = (datetime.now(timezone.utc) - created).days
            parts.append(f"User since: {days_active} days ago")
        
        return "\n".join(parts) if parts else ""
    
    def _build_goals_context(self, user_id: int) -> str:
        """Retrieve user goals and learning objectives."""
        goals = self.memory_manager.get_memory(user_id, "learning_goal")
        milestones = self.memory_manager.get_memory(user_id, "milestone")
        
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
        style = self.memory_manager.get_memory(user_id, "learning_style")
        tone = self.memory_manager.get_memory(user_id, "preferred_tone")
        frequency = self.memory_manager.get_memory(user_id, "contact_frequency")
        
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
        lessons_completed = self.memory_manager.get_memory(user_id, "lesson_completed")
        insights = self.memory_manager.get_memory(user_id, "insight")
        
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