"""
Memory Categories and Context Utilities

Provides helpers for memory management categories and prompt context optimization.
"""

from enum import Enum
from typing import List


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


class ConversationContextBuilder:
    """Helpers for building multi-turn conversation context."""
    
    @staticmethod
    def format_conversation_turn(user_msg: str, assistant_msg: str) -> str:
        """Format a single conversation exchange."""
        return f"User: {user_msg}\n\nAssistant: {assistant_msg}"
    

class ContextOptimizer:
    """Utility helpers for estimating tokens and preparing context text for prompts.

    These methods use simple, deterministic heuristics suitable for tests and
    coarse token-based truncation rather than a full tokenizer.
    """

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Return a rough token estimate using a characters->token heuristic.

        Heuristic used in tests: ~4 characters per token.
        """
        if not text:
            return 0
        return max(0, len(text) // 4)

    @staticmethod
    def truncate_by_tokens(text: str, max_tokens: int) -> str:
        """Truncate `text` so it is roughly within `max_tokens` using the
        same 4-chars-per-token heuristic. Truncation tries to avoid cutting
        a word in half by trimming to the last space if possible.
        """
        if not text:
            return ""
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text
        # Truncate and try to keep whole words
        truncated = text[:max_chars]
        # If next char is not whitespace and there is a space in truncated,
        # trim back to the last space to avoid splitting words.
        if not truncated.endswith(" ") and " " in truncated:
            truncated = truncated.rsplit(" ", 1)[0]
        return truncated

    @staticmethod
    def format_memory_list(memories: List[dict], max_items: int = 5) -> str:
        """Format a list of memory dicts for inclusion in a prompt.

        Each memory is expected to be a dict with keys `value` and
        `confidence` (0.0-1.0). Returns up to `max_items` lines with
        confidence shown as a percentage.
        """
        if not memories:
            return ""
        lines = []
        for m in memories[:max_items]:
            value = m.get("value", "")
            conf = m.get("confidence", None)
            if isinstance(conf, (int, float)) and conf is not None:
                pct = int(round(conf * 100))
                lines.append(f"{value} — {pct}%")
            else:
                lines.append(f"{value}")
        return "\n".join(lines)

