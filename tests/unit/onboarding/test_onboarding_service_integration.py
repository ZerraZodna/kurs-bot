"""Unit tests for onboarding service integration.

Migrated from tests/test_onboarding_service_integration.py to use new test fixtures.
"""

import pytest

from src.memories import MemoryManager
from src.onboarding import OnboardingService
from src.lessons.state import get_current_lesson

from tests.fixtures.users import create_test_user


class TestOnboardingServiceIntegration:
    """Tests for onboarding service integration."""

    def test_persist_explicit_lesson_number(self, db_session):
        """Given: A user
        When: Handling explicit lesson number response
        Then: Should persist the lesson number
        """
        # Given: A user
        user_id = create_test_user(db_session, "test_onboarding_service_int", "Test")
        
        mm = MemoryManager(db_session)
        svc = OnboardingService(db_session)
        
        # Ensure no current_lesson initially
        assert get_current_lesson(mm, user_id) is None
        
        # When: User indicates an explicit lesson
        res = svc.handle_lesson_status_response(user_id, "I am on lesson 6")
        
        # Then: Should return send_specific_lesson action
        assert res["action"] == "send_specific_lesson"
        
        # And: current_lesson should be persisted
        cur = get_current_lesson(mm, user_id)
        assert cur == 6

    def test_persist_continuing_when_completed_before(self, db_session):
        """Given: A user
        When: User says they've completed the course
        Then: Should return ask_lesson_number action
        """
        # Given: A user
        user_id = create_test_user(db_session, "test_onboarding_service_int2", "Test")
        
        mm = MemoryManager(db_session)
        svc = OnboardingService(db_session)
        
        # When: User says they've completed the course
        res = svc.handle_lesson_status_response(user_id, "I've completed the course")
        
        # Then: Should return ask_lesson_number action
        assert res["action"] == "ask_lesson_number"
        
        # And: current_lesson should be "continuing"
        cur = get_current_lesson(mm, user_id)
        assert cur == "continuing"

