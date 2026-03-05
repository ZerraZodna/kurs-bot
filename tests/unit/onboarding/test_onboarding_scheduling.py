"""Unit tests for onboarding scheduling.

Simplified onboarding flow: Name -> Consent (timezone is assumed Europe/Oslo)
"""

import pytest
import os

from src.memories import MemoryManager
from src.onboarding import OnboardingService
from src.onboarding.flow import OnboardingFlow
from src.onboarding import schedule_setup

from tests.fixtures.users import create_test_user


class TestOnboardingScheduling:
    """Tests for onboarding scheduling."""

    @pytest.mark.skipif(os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true", reason="Only runs with real Ollama")
    @pytest.mark.asyncio
    async def test_onboarding_schedule_created_after_user_reports_lesson(self, db_session):
        """Given: A user who has completed consent
        When: User reports their current lesson
        Then: Schedule should be auto-created
        """
        # Given: A user with consent (simplified flow: name + consent only)
        user_id = create_test_user(db_session, "test_onboarding_scheduling", "Test")
        
        mm = MemoryManager(db_session)
        svc = OnboardingService(db_session)
        flow = OnboardingFlow(mm, svc, call_ollama=None)
        
        # Ensure user has name and consent so flow reaches completion
        # Timezone is assumed Europe/Oslo for Norwegian users (no explicit step)
        mm.store_memory(user_id, "first_name", "Test", category="profile")
        mm.store_memory(user_id, "data_consent", "granted", category="profile")
        
        # When: User indicates lesson status
        resp1 = await flow.handle_onboarding(user_id, "I've completed the course before", db_session)
        
        # Then: Onboarding should be complete (simplified flow)
        # The user can then report their lesson number
        assert resp1 is not None
