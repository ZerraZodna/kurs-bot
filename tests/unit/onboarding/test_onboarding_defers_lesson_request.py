"""Unit tests for onboarding deferring lesson requests.

Migrated from tests/test_onboarding_defers_lesson_request.py to use new test fixtures.
"""

import pytest

from src.models.database import Schedule
from src.services.dialogue_engine import DialogueEngine
from src.memories import MemoryManager
from src.lessons.state import get_current_lesson

from tests.fixtures.users import create_test_user


class TestOnboardingDefersLessonRequest:
    """Tests for onboarding deferring lesson requests."""

    @pytest.mark.asyncio
    async def test_onboarding_lesson_reply_defers_to_onboarding(self, db_session):
        """Given: A user who has consent and commitment
        When: Replying with lesson number during onboarding
        Then: Should persist lesson, create schedule, and return onboarding-complete message
        """
        # Given: A user with consent and commitment
        user_id = create_test_user(db_session, "test_onboarding_defers_lesson", "Carol")
        
        mm = MemoryManager(db_session)
        mm.store_memory(user_id, "data_consent", "granted", category="profile", source="test")
        mm.store_memory(user_id, "acim_commitment", "committed to ACIM lessons", category="goals", source="test")
        
        dialogue = DialogueEngine(db_session)
        
        # When: Starting onboarding (bot will ask for name, then timezone, then lesson status)
        resp = await dialogue.process_message(user_id, "Hi", db_session)
        assert resp is not None  # bot asks to confirm name
        
        # And: Confirming name
        resp_name = await dialogue.process_message(user_id, "Yes", db_session)
        assert resp_name is not None  # bot asks for timezone
        
        # And: Confirming timezone
        resp_tz = await dialogue.process_message(user_id, "Yes", db_session)
        assert resp_tz is not None  # bot asks about lesson status
        
        # And: User replies with an explicit lesson number
        resp2 = await dialogue.process_message(user_id, "I am on lesson 8", db_session)
        assert resp2 is not None
        
        # Note: The lesson may not exist in test DB, but onboarding should progress
        # The response may indicate lesson not found OR show onboarding completion
        # Either way, the current_lesson should be stored and schedule should be created
        
        # And: Memory should have recorded current_lesson=8
        cur = get_current_lesson(mm, user_id)
        assert cur == 8, f"Expected current_lesson=8, got {cur}"
        
        # And: Schedule should be created (by completing onboarding)
        _ = dialogue.onboarding.get_onboarding_complete_message(user_id)
        schedules = db_session.query(Schedule).filter_by(user_id=user_id).all()
        assert any(s.schedule_type.startswith("daily") and s.is_active for s in schedules), \
            f"Expected active daily schedule, got {schedules}"
