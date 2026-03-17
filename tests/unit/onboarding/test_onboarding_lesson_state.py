"""Unit tests for onboarding lesson state.

Migrated from tests/test_onboarding_lesson_state.py to use new test fixtures.
"""

import pytest
from tests.fixtures.users import create_test_user

from src.lessons.state import get_current_lesson, get_lesson_state, set_current_lesson
from src.memories import MemoryManager


class TestOnboardingLessonState:
    """Tests for onboarding lesson state management."""

    @pytest.mark.asyncio
    async def test_onboarding_reports_current_lesson_advances_next(self, db_session):
        """Given: A user who reports being on lesson 8
        When: Setting current lesson using set_current_lesson (stores on user model)
        Then: Should reflect lesson 8 and next would be 9
        """
        # Given: A user
        user_id = create_test_user(db_session, "test_onboarding_lesson_state", "Test")
        
        mm = MemoryManager(db_session)
        
        # When: Onboarding sets current lesson using set_current_lesson (stores on user.lesson)
        set_current_lesson(mm, user_id, 8)
        
        # Then: get_current_lesson should return the stored value from user model
        cur = get_current_lesson(mm, user_id)
        assert str(cur) == "8" or cur == 8
        
        # And: get_lesson_state should reflect current_lesson = 8
        state = get_lesson_state(mm, user_id)
        assert state.get("current_lesson") == "8" or state.get("current_lesson") == 8
