"""Unit tests for onboarding deferring lesson requests.

Simplified onboarding flow: Name -> Consent
"""

import pytest
import os

from src.models.database import Schedule
from src.services.dialogue_engine import DialogueEngine
from src.memories import MemoryManager
from src.lessons.state import get_current_lesson

from tests.fixtures.users import make_ready_user


class TestOnboardingDefersLessonRequest:
    """Tests for onboarding deferring lesson requests."""

    @pytest.mark.skipif(os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true", reason="Only runs with real Ollama")
    @pytest.mark.asyncio
    async def test_onboarding_lesson_reply_defers_to_onboarding(self, db_session):
        """Given: A user who has consent
        When: Replying with lesson number after onboarding
        """
        # Given: A user with consent (simplified flow: name + consent only)
        user_id = make_ready_user(db_session, "test_onboarding_defers_lesson", "Carol")
        
        mm = MemoryManager(db_session)
        
        dialogue = DialogueEngine(db_session)
        
        # And: User replies with an explicit lesson number (post-onboarding)
        result = await dialogue.process_message(user_id, "I am on lesson 8", db_session)

        # Consume the stream and call the post_hook so function calls are executed
        if result.get("type") == "stream":
            full_response = ""
            async for token in result["generator"]:
                full_response += token
            await result["post_hook"](full_response)
        # For non-stream responses (text type), no post_hook to call

        # And: Memory should have recorded current_lesson=8
        cur = get_current_lesson(mm, user_id)
        assert cur == 8, f"Expected current_lesson=8, got {cur}"
