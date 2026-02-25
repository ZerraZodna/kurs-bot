"""Unit tests for onboarding scheduling.

Migrated from tests/test_onboarding_scheduling.py to use new test fixtures.
"""

import pytest

from src.memories import MemoryManager
from src.onboarding import OnboardingService
from src.onboarding.flow import OnboardingFlow
from src.onboarding import schedule_setup

from tests.fixtures.users import create_test_user


class TestOnboardingScheduling:
    """Tests for onboarding scheduling."""

    @pytest.mark.asyncio
    async def test_onboarding_schedule_created_after_user_reports_lesson(self, db_session):
        """Given: A user who has completed consent and commitment
        When: User reports their current lesson
        Then: Schedule should be auto-created
        """
        # Given: A user with consent and commitment
        user_id = create_test_user(db_session, "test_onboarding_scheduling", "Test")
        
        mm = MemoryManager(db_session)
        svc = OnboardingService(db_session)
        flow = OnboardingFlow(mm, svc, call_ollama=None)
        
        # Ensure user has name, consent and commitment so flow reaches lesson_status
        mm.store_memory(user_id, "first_name", "Test", category="profile")
        mm.store_memory(user_id, "data_consent", "granted", category="profile")
        mm.store_memory(user_id, "acim_commitment", "committed to ACIM lessons", category="goals")
        
        # When: User indicates they've completed the course
        resp1 = await flow.handle_onboarding(user_id, "I've completed the course before", db_session)
        assert isinstance(resp1, str)
        assert "lesson" in resp1.lower() or "which lesson" in resp1.lower()
        
        # And: User provides explicit lesson number
        resp2 = await flow.handle_onboarding(user_id, "I am on lesson 6", db_session)
        
        # Then: Schedule should exist (07:30 default)
        sched = schedule_setup.check_existing_schedule(db_session, user_id)
        assert sched is not None, "Expected an auto-created daily schedule after user reported a lesson"

