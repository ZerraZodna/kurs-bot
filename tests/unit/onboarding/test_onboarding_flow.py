"""Unit tests for onboarding flow.

Simplified onboarding flow: Name -> Consent
"""

import pytest
import os
from datetime import datetime, timezone

from src.models.database import User, Memory, Schedule
from src.services.dialogue_engine import DialogueEngine
from src.memories import MemoryManager
from src.lessons.state import get_current_lesson
from tests.fixtures.users import create_test_user


class TestOnboardingFlow:
    """Tests for the onboarding flow."""

    @pytest.mark.skipif(os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true", reason="Only runs with real Ollama")
    @pytest.mark.asyncio
    async def test_onboarding_new_user_creates_daily_schedule(self, db_session):
        """Given: A new user
        When: Completing onboarding (name + consent)
        Then: Should create a daily schedule
        """
        # Given: A new user
        user_id = create_test_user(db_session, external_id="test_onboarding_flow_new_user", first_name="Alice")
        dialogue = DialogueEngine(db_session)
        
        # When: Starting onboarding with greeting
        # Simplified flow: Hi → name confirmation → consent → complete
        resp = await dialogue.process_message(user_id, "Hi", db_session)
        assert resp is not None  # bot asks to confirm name

        # And: Confirming name (step 1 of onboarding)
        resp_name = await dialogue.process_message(user_id, "Yes", db_session)
        assert resp_name is not None  # bot asks for consent

        # And: Granting consent (step 2 of onboarding)
        resp2 = await dialogue.process_message(user_id, "Yes", db_session)
        assert resp2 is not None  # onboarding complete
        
        # Then: Should have an active daily schedule
        # (timezone is assumed Europe/Oslo)
        db_session.expire_all()
        schedules = db_session.query(Schedule).filter_by(user_id=user_id).all()
        assert any(s.schedule_type.startswith("daily") and s.is_active for s in schedules), \
            f"Expected active daily schedule, got {schedules}"


    @pytest.mark.skipif(os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true", reason="Only runs with real Ollama")
    @pytest.mark.asyncio
    async def test_onboarding_new_user_norwegian(self, db_session):
        """Given: A Norwegian-speaking user
        When: Going through onboarding in Norwegian
        Then: Should receive Norwegian prompts and complete
        """
        # Given: A Norwegian user
        user = User(
            external_id="test_onboarding_flow_norwegian_v2",
            channel="telegram",
            first_name="Ola",
            opted_in=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        db_session.commit()
        
        dialogue = DialogueEngine(db_session)
        
        # When: Sending Norwegian greeting
        # Simplified flow: Hei → name confirmation → consent → complete
        resp1 = await dialogue.process_message(user.user_id, "Hei", db_session)
        assert resp1 is not None  # bot asks to confirm name ("Er det greit at jeg kaller deg Ola?")

        # And: Confirming name
        resp_name = await dialogue.process_message(user.user_id, "Ja", db_session)
        assert resp_name is not None  # bot asks for consent (contains "ja/nei")
        
        # And: Responding yes to consent
        resp2 = await dialogue.process_message(user.user_id, "Ja", db_session)
        assert resp2 is not None  # onboarding complete
        
        # Then: Should have an active daily schedule
        db_session.expire_all()
        schedules = db_session.query(Schedule).filter_by(user_id=user.user_id).all()
        assert any(s.schedule_type.startswith("daily") and s.is_active for s in schedules), \
            f"Expected active daily schedule, got {schedules}"

