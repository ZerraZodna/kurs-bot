"""
Memory Categories and Context Utilities

Provides helpers for memory management categories and prompt context optimization.
"""

from enum import Enum
from typing import List, Dict, Optional
import json


class MemoryCategory(str, Enum):
    """Standard memory categories for organized user context."""
    PROFILE = "profile"                    # Name, age, location, contact info
    GOALS = "goals"                        # Learning goals, objectives
    PREFERENCES = "preferences"            # Communication style, frequency, interests
    PROGRESS = "progress"                  # Lessons completed, milestones
    INSIGHTS = "insights"                  # AI-derived understanding, patterns
    CONVERSATION = "conversation"          # Recent conversation context


class MemoryKey:
    """Standard memory keys for consistent data retrieval."""
    
    # Profile category
    FULL_NAME = "full_name"
    TIMEZONE = "timezone"
    LANGUAGE = "language"
    ACCESSIBILITY_NEEDS = "accessibility_needs"
    
    # Goals category
    LEARNING_GOAL = "learning_goal"
    LEARNING_STYLE = "learning_style"
    MILESTONE = "milestone"
    COMPLETION_RATE = "completion_rate"
    
    # Preferences category
    PREFERRED_TONE = "preferred_tone"
    CONTACT_FREQUENCY = "contact_frequency"
    LESSON_DIFFICULTY = "lesson_difficulty"
    COMMUNICATION_METHOD = "communication_method"
    
    # Progress category
    LESSON_COMPLETED = "lesson_completed"
    PRACTICE_STREAK = "practice_streak"
    MASTERY_LEVEL = "mastery_level"
    LAST_SESSION_DATE = "last_session_date"
    
    # Insights category
    LEARNING_PATTERN = "learning_pattern"
    ENGAGEMENT_LEVEL = "engagement_level"
    KNOWLEDGE_GAP = "knowledge_gap"
    STRENGTH_AREA = "strength_area"
    
    # Conversation category
    LAST_TOPIC = "last_topic"
    OPEN_QUESTIONS = "open_questions"
    CONVERSATION_STATE = "conversation_state"


class ContextOptimizer:
    """Utility for optimizing context and prompt formatting."""
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Rough token count estimate (4 chars ≈ 1 token for most LLMs).
        For accurate counts, use tiktoken or your model's tokenizer.
        """
        return len(text) // 4
    
    @staticmethod
    def truncate_by_tokens(text: str, max_tokens: int) -> str:
        """Truncate text to approximately max_tokens."""
        estimated_chars = max_tokens * 4
        if len(text) <= estimated_chars:
            return text
        return text[:estimated_chars].rsplit(' ', 1)[0] + "..."
    
    @staticmethod
    def format_memory_list(memories: List[Dict], max_items: int = 5) -> str:
        """Format a list of memories for prompt inclusion."""
        if not memories:
            return ""
        
        lines = []
        for i, memory in enumerate(memories[:max_items], 1):
            value = memory.get("value", "")
            confidence = memory.get("confidence", 1.0)
            
            # Include confidence if less than 100%
            if confidence < 1.0:
                lines.append(f"{i}. {value} (confidence: {confidence:.0%})")
            else:
                lines.append(f"{i}. {value}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_json_memory(data: Dict, indent: int = 0) -> str:
        """Format structured memory as readable text."""
        try:
            if isinstance(data.get("value"), str):
                # Try to parse JSON string
                parsed = json.loads(data["value"])
                return json.dumps(parsed, indent=2)
        except (json.JSONDecodeError, TypeError):
            pass
        
        return data.get("value", str(data))


class ConversationContextBuilder:
    """Helpers for building multi-turn conversation context."""
    
    @staticmethod
    def format_conversation_turn(user_msg: str, assistant_msg: str) -> str:
        """Format a single conversation exchange."""
        return f"User: {user_msg}\n\nAssistant: {assistant_msg}"
    
    @staticmethod
    def format_conversation_thread(turns: List[tuple]) -> str:
        """Format multiple conversation turns."""
        formatted = []
        for user_msg, assistant_msg in turns:
            formatted.append(ConversationContextBuilder.format_conversation_turn(user_msg, assistant_msg))
        return "\n\n".join(formatted)
    
    @staticmethod
    def summarize_conversation(turns: List[tuple], max_summary_length: int = 150) -> str:
        """
        Create a brief summary of conversation thread.
        Useful when full history exceeds token limits.
        """
        if not turns:
            return ""
        
        # Simple extraction of key topics/intents
        topics = []
        for user_msg, _ in turns:
            # Extract first few words as topic indicator
            words = user_msg.split()[:5]
            topic = " ".join(words)
            if topic not in topics:
                topics.append(topic)
        
        summary = "Previous topics discussed: " + ", ".join(topics[:3])
        return summary[:max_summary_length]


class PromptTemplate:
    """Pre-built prompt templates for common scenarios."""
    
    @staticmethod
    def dialogue_template(system_prompt: str, user_context: str, user_input: str) -> str:
        """Standard dialogue template."""
        return f"""{system_prompt}

{user_context}

User: {user_input}"""