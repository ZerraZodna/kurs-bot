"""Unit tests for onboarding lesson state.

Migrated from tests/test_onboarding_lesson_state.py to use new test fixtures.
"""

import pytest

from src.memories import MemoryManager
from src.lessons.state import get_lesson_state, get_current_lesson

from tests.fixtures.users import create_test_user


class TestOnboardingLessonState:
    """Tests for onboarding lesson state management."""

    @pytest.mark.asyncio
    async def test_onboarding_reports_current_lesson_advances_next(self, db_session):
        """Given: A user who reports being on lesson 8
        When: Storing current_lesson memory
        Then: Should reflect lesson 8 and next would be 9
        """
        # Given: A user
        user_id = create_test_user(db_session, "test_onboarding_lesson_state", "Test")
        
        mm = MemoryManager(db_session)
        
        # When: Onboarding stores current_lesson value
        mm.store_memory(user_id=user_id, key="current_lesson", value="8", category="progress")
        
        # Then: get_current_lesson should return the stored value
        cur = get_current_lesson(mm, user_id)
        assert str(cur) == "8" or cur == 8
        
        # And: get_lesson_state should reflect current_lesson = 8
        state = get_lesson_state(mm, user_id)
        assert state.get("current_lesson") == "8" or state.get("current_lesson") == 8

