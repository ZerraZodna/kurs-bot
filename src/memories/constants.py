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


class MemoryKey:
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    NAME = "name"
    USER_LANGUAGE = "user_language"
    LEARNING_GOAL = "learning_goal"
    ACIM_COMMITMENT = "acim_commitment"
    DATA_CONSENT = "data_consent"
    PREFERRED_LESSON_TIME = "preferred_lesson_time"

    CURRENT_LESSON = "current_lesson"
    LESSON_COMPLETED = "lesson_completed"
    LESSON_STATE = "lesson_state"
    LAST_SENT_LESSON_ID = "last_sent_lesson_id"
    LESSON_CONFIRMATION_PENDING = "lesson_confirmation_pending"

    SCHEDULE_MESSAGE = "schedule_message"
    SCHEDULE_REQUEST_PENDING = "schedule_request_pending"
    DELETE_SCHEDULES_PENDING = "delete_schedules_pending"
    TRIGGER_AUDIT = "trigger_audit"

    RAG_MODE_ENABLED = "rag_mode_enabled"
    SELECTED_RAG_PROMPT_KEY = "selected_rag_prompt_key"
    CUSTOM_RAG_PROMPT = "custom_rag_prompt"
    DEBUG_DAY_OFFSET = "debug_day_offset"
    ONBOARDING_STEP_PENDING = "onboarding_step_pending"
    ONBOARDING_COMPLETE_MESSAGE_SENT = "onboarding_complete_message_sent"
    PENDING_LESSON_DELIVERY = "pending_lesson_delivery"

    FULL_NAME = "full_name"
    PERSONAL_BACKGROUND = "personal_background"
    MILESTONE = "milestone"
    LEARNING_STYLE = "learning_style"
    PREFERRED_TONE = "preferred_tone"
    CONTACT_FREQUENCY = "contact_frequency"
    INSIGHT = "insight"
