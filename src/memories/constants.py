"""Centralized memory keys and categories."""

from __future__ import annotations

from enum import Enum


class MemoryCategory(str, Enum):
    FACT = "fact"
    PROFILE = "profile"
    GOALS = "goals"
    PREFERENCE = "preference"
    PREFERENCES = "preferences"
    PROGRESS = "progress"
    INSIGHTS = "insights"
    CONVERSATION = "conversation"
    AUDIT = "audit"

    @classmethod
    def is_valid(cls, category: str) -> bool:
        """Check if a category string is valid."""
        return category in {c.value for c in cls}

    @classmethod
    def normalize(cls, category: str) -> str:
        """Normalize a category string to a valid value."""
        if not category:
            return cls.FACT.value
        
        normalized = category.lower().strip()
        
        # Handle common aliases
        aliases = {
            "preferences": cls.PREFERENCES.value,
            "pref": cls.PREFERENCE.value,
            "goal": cls.GOALS.value,
            "goals": cls.GOALS.value,
            "learning_goal": cls.GOALS.value,
            "profile": cls.PROFILE.value,
            "fact": cls.FACT.value,
            "facts": cls.FACT.value,
            "progress": cls.PROGRESS.value,
            "insight": cls.INSIGHTS.value,
            "insights": cls.INSIGHTS.value,
            "conversation": cls.CONVERSATION.value,
            "chat": cls.CONVERSATION.value,
            "audit": cls.AUDIT.value,
        }
        
        return aliases.get(normalized, cls.FACT.value)


class MemoryKey:
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    NAME = "name"
    FULL_NAME = "full_name"
    USER_LANGUAGE = "user_language"
    LANGUAGE = "language"
    LEARNING_GOAL = "learning_goal"
    DATA_CONSENT = "data_consent"
    PERSONAL_BACKGROUND = "personal_background"

    PREFERRED_LESSON_TIME = "preferred_lesson_time"
    LESSON_CURRENT = "current_lesson"
    LESSON_COMPLETED = "lesson_completed"
    LESSON_CONFIRMATION_PENDING = "lesson_confirmation_pending"

    SCHEDULE_MESSAGE = "schedule_message"
    SCHEDULE_REQUEST_PENDING = "schedule_request_pending"
    DELETE_SCHEDULES_PENDING = "delete_schedules_pending"
    DELETE_SCHEDULES_TYPE_PENDING = "delete_schedules_type_pending"
    TRIGGER_AUDIT = "trigger_audit"

    RAG_MODE_ENABLED = "rag_mode_enabled"
    SELECTED_RAG_PROMPT_KEY = "selected_rag_prompt_key"
    CUSTOM_RAG_PROMPT = "custom_rag_prompt"
    ONBOARDING_STEP_PENDING = "onboarding_step_pending"
    ONBOARDING_COMPLETE_MESSAGE_SENT = "onboarding_complete_message_sent"
    PENDING_LESSON_DELIVERY = "pending_lesson_delivery"

    MILESTONE = "milestone"
    PREFERRED_TONE = "preferred_tone"
    COMMUNICATION_METHOD = "communication_method"

    # Lesson repeat tracking
    LESSON_REPEAT_OFFERED = "lesson_repeat_offered"
