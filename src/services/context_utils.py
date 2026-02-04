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
    
