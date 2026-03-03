"""Updated unit tests for onboarding service with correct flow order: Name -> Consent -> Timezone."""

import pytest
from datetime import datetime, timezone

from src.models.database import User, Schedule
from src.services.dialogue_engine import DialogueEngine
from src.memories import MemoryManager
from src.scheduler import SchedulerService
from src.lessons.state import get_current_lesson

from tests.fixtures.users import create_test_user


class TestOnboarding:
    """Tests for the onboarding service."""

    @pytest.mark.asyncio
    async def test_complete_onboarding_flow(self, db_session):
        """Given: A new user
        When: Going through complete onboarding flow
        Then: Should complete onboarding and create schedule
        """
        # Given: A new user
        user_id = create_test_user(db_session, "test_onboarding_complete_flow", "Sarah")
        
        dialogue = DialogueEngine(db_session)
        
        # When: User sends first message
        # Step 1: First message - should get welcome/name prompt
        response = await dialogue.process_message(user_id, "Hi there!", db_session)
        assert response is not None
        
        # Step 2: User provides name
        response = await dialogue.process_message(user_id, "My name is Sarah", db_session)
        assert response is not None
        
        # Step 3: User consents to data storage
        response = await dialogue.process_message(user_id, "Yes, I consent", db_session)
        assert response is not None
        
        # Step 4: User confirms timezone
        response = await dialogue.process_message(user_id, "Yes", db_session)
        assert response is not None
        # Verify timezone was set
        user = db_session.query(User).filter_by(user_id=user_id).first()
        assert user.timezone is not None, "Timezone should be set after confirmation"
        
        # Step 5: User commits to lessons

        response = await dialogue.process_message(user_id, "Yes, I'm ready to commit to this journey!", db_session)
        assert response is not None
        
        # Step 6: User provides lesson status (new vs continuing) - says "new"
        response = await dialogue.process_message(user_id, "I'm new to ACIM", db_session)
        assert response is not None
        
        # Step 7: Handle the intro offer (new user gets offer for Lesson 0)
        # Accept the introduction offer
        response = await dialogue.process_message(user_id, "yes", db_session)
        assert response is not None
        
        # Then: Schedule should be auto-created
        db_session.expire_all()
        schedules = db_session.query(Schedule).filter_by(user_id=user_id).all()
        assert len(schedules) > 0, "Expected schedule to be created"
        assert any(s.schedule_type.startswith("daily") and s.is_active for s in schedules), \
            f"Expected active daily schedule, got {schedules}"

    @pytest.mark.asyncio
    async def test_consent_granted_continues_onboarding(self, db_session):
        """Given: A new user
        When: Consenting to data storage
        Then: Should show thank-you and continue to commitment
        """
        # Given: A new user
        user_id = create_test_user(db_session, "test_onboarding_consent", "Alex")
        
        dialogue = DialogueEngine(db_session)
        
        # When: Triggering name prompt and providing name
        response = await dialogue.process_message(user_id, "Hi", db_session)
        response = await dialogue.process_message(user_id, "My name is Alex", db_session)
        
        # And: Providing consent
        response = await dialogue.process_message(user_id, "Yes, I consent", db_session)
        
        # Then: Response should include localized thank-you or continue to next step
        # Note: After consent, the flow may show thank-you + next step (timezone or commitment)
        assert (
            "Thank you for consenting" in response
            or "Are you interested" in response
            or "Are you new to ACIM" in response
            or "Are you ready" in response
            or "commit" in response.lower()
            or "timezone" in response.lower()
            or "assume you're in" in response.lower()
        ), f"Expected onboarding continuation after consent, got: {response}"

    @pytest.mark.asyncio
    async def test_schedule_request(self, db_session):
        """Given: A user
        When: Requesting reminders explicitly
        Then: Bot should guide through setup (first getting name, then consent, timezone, commitment, lesson status)
        """
        # Given: A user (no first_name memory stored, so bot will ask for name first)
        user = User(
            external_id="test_onboarding_schedule_request",
            channel="telegram",
            first_name="Test",
            opted_in=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        db_session.commit()

        dialogue = DialogueEngine(db_session)

        # When: User asks for reminders
        response = await dialogue.process_message(user.user_id, "Can you remind me to do my daily lesson?", db_session)

        # Then: Bot should first ask for name (onboarding must complete first)
        # The bot guides through onboarding before setting up schedules
        assert response is not None
        # Name is asked first since user has no name stored in memories
        assert "name" in response.lower() or "call you" in response.lower() or "test" in response.lower(), \
            f"Expected bot to ask for name first, got: {response}"

    def test_time_parsing(self):
        """Given: Various time strings
        When: Parsing time
        Then: Should return correct hour and minute
        """
        # Given/When: Test cases for time parsing
        test_cases = [
            ("9:00 AM", (9, 0)),
            ("2:30 PM", (14, 30)),
            ("morning", (9, 0)),
            ("evening", (19, 0)),
            ("21:00", (21, 0)),
            ("kvelden", (19, 0)),  # Norwegian
        ]
        
        # Then: All test cases should pass
        for time_str, expected in test_cases:
            result = SchedulerService.parse_time_string(time_str)
            assert result == expected, f"Expected {expected} for '{time_str}', got {result}"

    @pytest.mark.asyncio
    async def test_onboarding_greeting_hei_detects_norwegian(self, db_session):
        """Given: A new user
        When: Sending Norwegian greeting 'Hei'
        Then: Should detect Norwegian and respond in Norwegian
        """
        # Given: A new user (no first_name memory stored, so bot will ask for name in Norwegian)
        user = User(
            external_id="test_onboarding_norwegian_hei",
            channel="telegram",
            first_name="Test",
            opted_in=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        db_session.commit()

        mm = MemoryManager(db_session)

        # When: Sending Norwegian greeting
        dialogue = DialogueEngine(db_session)
        response = await dialogue.process_message(user.user_id, "Hei", db_session)

        # Then: Language memory should be Norwegian
        lang_memories = mm.get_memory(user.user_id, "user_language")
        assert lang_memories, "No user_language memory stored after greeting"
        assert any(m["value"].lower().startswith("no") for m in lang_memories), \
            f"Expected 'no' to be stored after message 'Hei', got: {[m['value'] for m in lang_memories]}"

        # And: Response should be in Norwegian
        assert (
            "navnet ditt i Telegram" in response
            or "Jeg ser at navnet ditt i Telegram" in response
            or "kaller deg" in response
            or "Hva heter du" in response
            or "Velkommen! Hva heter du" in response
            or ("Velkommen!" in response and "Hva" in response)
        ), f"Expected Norwegian onboarding prompt, got: {response}"
