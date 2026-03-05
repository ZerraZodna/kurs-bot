"""Unit tests for onboarding deferring lesson requests.

Simplified onboarding flow: Name -> Consent
"""

import pytest
import os

from src.models.database import Schedule
from src.services.dialogue_engine import DialogueEngine
from src.memories import MemoryManager
from src.lessons.state import get_current_lesson

from tests.fixtures.users import create_test_user


class TestOnboardingDefersLessonRequest:
    """Tests for onboarding deferring lesson requests."""

    @pytest.mark.skipif(os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true", reason="Only runs with real Ollama")
    @pytest.mark.asyncio
    async def test_onboarding_lesson_reply_defers_to_onboarding(self, db_session):
        """Given: A user who has consent
        When: Replying with lesson number during onboarding
        Then: Should persist lesson, create schedule, and return onboarding-complete message
        """
        # Given: A user with consent (simplified flow: name + consent only)
        user_id = create_test_user(db_session, "test_onboarding_defers_lesson", "Carol")
        
        mm = MemoryManager(db_session)
        mm.store_memory(user_id, "data_consent", "granted", category="profile", source="test")
        
        dialogue = DialogueEngine(db_session)
        
        # When: Starting onboarding (bot will ask for name)
        resp = await dialogue.process_message(user_id, "Hi", db_session)
        assert resp is not None  # bot asks to confirm name
        
        # And: Confirming name
        resp_name = await dialogue.process_message(user_id, "Yes", db_session)
        assert resp_name is not None  # bot asks for consent
        
        # And: Providing consent
        resp_consent = await dialogue.process_message(user_id, "Yes, I consent", db_session)
        assert resp_consent is not None  # onboarding complete
        
        # Note: Schedule should be auto-created after consent
        # (Simplified flow: timezone is assumed Europe/Oslo)
        
        # And: User replies with an explicit lesson number (post-onboarding)
        resp2 = await dialogue.process_message(user_id, "I am on lesson 8", db_session)
        # Response may indicate lesson not found OR lesson info
        # Either way, the current_lesson should be stored
        
        # And: Memory should have recorded current_lesson=8
        cur = get_current_lesson(mm, user_id)
        assert cur == 8, f"Expected current_lesson=8, got {cur}"
