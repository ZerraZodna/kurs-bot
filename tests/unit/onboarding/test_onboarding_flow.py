"""Unit tests for onboarding flow.

Migrated from tests/test_onboarding_flow.py to use new test fixtures.
"""

import pytest
from datetime import datetime, timezone

from src.models.database import User, Memory, Schedule
from src.services.dialogue_engine import DialogueEngine
from src.memories import MemoryManager
from src.lessons.state import get_current_lesson
from tests.fixtures.users import create_test_user


class TestOnboardingFlow:
    """Tests for the onboarding flow."""

    @pytest.mark.asyncio
    async def test_onboarding_new_user_creates_daily_schedule(self, db_session):
        """Given: A new user
        When: Completing onboarding with consent and commitment
        Then: Should create a daily schedule
        """
        # Given: A new user (create directly to avoid fixture conflicts)
        user = User(
            external_id="test_onboarding_flow_new_user",
            channel="telegram",
            first_name="Alice",
            opted_in=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        db_session.commit()
        
        user_id = user.user_id
        dialogue = DialogueEngine(db_session)
        
        # When: Starting onboarding with greeting
        # Flow: Hi → name confirmation → consent → commitment → lesson status → intro offer
        resp = await dialogue.process_message(user_id, "Hi", db_session)
        assert resp is not None  # bot asks to confirm name

        # And: Confirming name (step 1 of onboarding)
        resp_name = await dialogue.process_message(user_id, "Yes", db_session)
        assert resp_name is not None  # bot asks for consent

        # And: Granting consent
        resp2 = await dialogue.process_message(user_id, "Yes", db_session)
        assert resp2 is not None  # bot asks for commitment

        # And: Committing to lessons
        resp3 = await dialogue.process_message(user_id, "Yes", db_session)
        assert resp3 is not None  # bot asks about lesson status

        # And: Indicating new user → bot offers introduction (Lesson 0)
        resp4 = await dialogue.process_message(user_id, "new", db_session)
        assert resp4 is not None

        # Accept the intro
        resp5 = await dialogue.process_message(user_id, "yes", db_session)
        assert resp5 is not None
        
        # Then: Should have an active daily schedule
        # Refresh the session to see latest data
        db_session.expire_all()
        schedules = db_session.query(Schedule).filter_by(user_id=user_id).all()
        assert any(s.schedule_type.startswith("daily") and s.is_active for s in schedules), \
            f"Expected active daily schedule, got {schedules}"

    @pytest.mark.asyncio
    async def test_onboarding_continuing_user_lesson10_sets_memory_and_schedule(self, db_session):
        """Given: A user who is on lesson 10
        When: Completing onboarding
        Then: Should store current_lesson and create schedule
        """
        # Given: A user with consent and commitment already stored
        # Use unique external_id to avoid conflicts
        user = User(
            external_id="test_onboarding_flow_continuing_user_v2",
            channel="telegram",
            first_name="Bob",
            opted_in=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        db_session.commit()
        
        mm = MemoryManager(db_session)
        mm.store_memory(user.user_id, "data_consent", "granted", category="profile", source="test")
        mm.store_memory(user.user_id, "acim_commitment", "committed to ACIM lessons", category="goals", source="test")
        
        dialogue = DialogueEngine(db_session)
        
        # When: Starting onboarding
        # Flow: Hi → name confirmation → lesson status (consent+commitment already stored)
        resp = await dialogue.process_message(user.user_id, "Hi", db_session)
        assert resp is not None  # bot asks to confirm name

        # And: Confirming name
        resp_name = await dialogue.process_message(user.user_id, "Yes", db_session)
        assert resp_name is not None  # bot asks about lesson status

        # And: Stating current lesson
        resp2 = await dialogue.process_message(user.user_id, "I am on lesson 10", db_session)
        assert resp2 is not None
        
        # Then: Memory should have current_lesson=10
        mm = MemoryManager(db_session)
        cur = get_current_lesson(mm, user.user_id)
        assert cur == 10, f"Expected current_lesson=10, got {cur}"
        
        # When: Completing onboarding
        # Get the onboarding complete message (this triggers schedule creation)
        _ = dialogue.onboarding.get_onboarding_complete_message(user.user_id)
        
        # Then: Should have a daily schedule
        # Refresh session to get latest data after potential schedule creation
        db_session.expire_all()
        schedules = db_session.query(Schedule).filter_by(user_id=user.user_id).all()
        assert any(s.schedule_type.startswith("daily") and s.is_active for s in schedules), \
            f"Expected active daily schedule, got {schedules}"

    @pytest.mark.asyncio
    async def test_onboarding_new_user_can_decline_intro_and_still_complete(self, db_session):
        """Given: A new user who declines the introduction
        When: Completing onboarding
        Then: Should still complete and create schedule
        """
        # Given: A new user (create directly with unique external_id)
        user = User(
            external_id="test_onboarding_flow_decline_intro",
            channel="telegram",
            first_name="Alice",
            opted_in=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        db_session.commit()
        
        user_id = user.user_id
        dialogue = DialogueEngine(db_session)
        
        # When: Going through onboarding
        # Flow: Hi → name confirmation → consent → commitment → lesson status → intro offer
        assert await dialogue.process_message(user_id, "Hi", db_session) is not None   # name confirmation
        assert await dialogue.process_message(user_id, "Yes", db_session) is not None  # consent
        assert await dialogue.process_message(user_id, "Yes", db_session) is not None  # commitment
        assert await dialogue.process_message(user_id, "Yes", db_session) is not None  # lesson status

        # After lesson status, the bot asks about new vs continuing
        # The user says "new" → bot offers introduction
        intro_offer = await dialogue.process_message(user_id, "new", db_session)
        assert intro_offer is not None

        # Decline the intro
        decline_intro = await dialogue.process_message(user_id, "no", db_session)
        assert decline_intro is not None
        
        # Then: Should still have an active daily schedule
        db_session.expire_all()
        schedules = db_session.query(Schedule).filter_by(user_id=user_id).all()
        assert any(s.schedule_type.startswith("daily") and s.is_active for s in schedules), \
            f"Expected active daily schedule, got {schedules}"

    @pytest.mark.asyncio
    async def test_onboarding_new_user_norwegian_gets_intro_offer_and_introduction(self, db_session):
        """Given: A Norwegian-speaking user
        When: Going through onboarding in Norwegian
        Then: Should receive Norwegian prompts and offer introduction
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
        # Flow: Hei → name confirmation → consent → commitment → lesson status → intro offer
        resp1 = await dialogue.process_message(user.user_id, "Hei", db_session)
        assert resp1 is not None  # bot asks to confirm name ("Er det greit at jeg kaller deg Ola?")

        # And: Confirming name
        resp_name = await dialogue.process_message(user.user_id, "Ja", db_session)
        assert resp_name is not None  # bot asks for consent (contains "ja/nei")
        assert "ja/nei" in resp_name.lower() or "gdpr" in resp_name.lower()

        # And: Responding yes to consent
        resp2 = await dialogue.process_message(user.user_id, "Ja", db_session)
        assert resp2 is not None  # bot asks for commitment

        # And: Responding yes to commitment
        resp3 = await dialogue.process_message(user.user_id, "Ja", db_session)
        assert resp3 is not None  # bot asks about lesson status
        assert "er du ny" in resp3.lower() or "acim" in resp3.lower() or "leksjon" in resp3.lower()

        # And: Saying "I'm new" → bot offers introduction
        resp4 = await dialogue.process_message(user.user_id, "Jeg er ny", db_session)
        assert resp4 is not None
        assert "introduksjon" in resp4.lower()
        assert "ja/nei" in resp4.lower()

        # And: Accepting introduction
        resp5 = await dialogue.process_message(user.user_id, "Ja", db_session)
        assert resp5 is not None
        assert "introduksjon" in resp5.lower() or "introduction" in resp5.lower()

