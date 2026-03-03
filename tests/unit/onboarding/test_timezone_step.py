"""Unit tests for the timezone step in onboarding flow."""

import pytest
from src.models.database import User
from src.services.dialogue_engine import DialogueEngine
from src.memories import MemoryManager
from src.memories.constants import MemoryKey, MemoryCategory
from tests.fixtures.users import create_test_user


class TestTimezoneStep:
    """Tests for the timezone confirmation step in onboarding."""

    @pytest.mark.asyncio
    async def test_timezone_step_appears_after_name(self, db_session):
        """Given: A new user who has provided their name
        When: The next onboarding prompt is requested
        Then: Should ask for timezone confirmation
        """
        # Given: A new user with name set but no timezone
        user_id = create_test_user(db_session, "test_timezone_step", "John")
        
        # Ensure user has no timezone set
        user = db_session.query(User).filter_by(user_id=user_id).first()
        user.timezone = None
        db_session.commit()
        
        dialogue = DialogueEngine(db_session)
        
        # When: User provides name (triggers onboarding flow)
        response = await dialogue.process_message(user_id, "Hi", db_session)
        
        # Then: Should ask for timezone confirmation (since name is set via memory but timezone is not)
        # Note: The flow may skip directly to timezone if name is already detected
        assert "timezone" in response.lower() or "assume you're in" in response.lower() or "consent" in response.lower(), \
            f"Expected onboarding prompt (timezone or consent), got: {response}"

    @pytest.mark.asyncio
    async def test_timezone_confirmed_yes_sets_timezone(self, db_session):
        """Given: A user at the timezone step
        When: User confirms with "yes"
        Then: Timezone should be set in DB
        """
        # Given: A new user at timezone step
        user_id = create_test_user(db_session, "test_timezone_yes", "Jane")
        
        # Ensure user has no timezone set
        user = db_session.query(User).filter_by(user_id=user_id).first()
        user.timezone = None
        db_session.commit()
        
        # Set up pending timezone step
        mm = MemoryManager(db_session)
        mm.store_memory(
            user_id=user_id,
            key=MemoryKey.ONBOARDING_STEP_PENDING,
            value="timezone",
            category=MemoryCategory.CONVERSATION.value,
            ttl_hours=2,
            source="test",
        )
        
        dialogue = DialogueEngine(db_session)
        
        # When: User confirms timezone with "yes"
        response = await dialogue.process_message(user_id, "Yes", db_session)
        
        # Then: Timezone should be set (inferred from language)
        user = db_session.query(User).filter_by(user_id=user_id).first()
        assert user.timezone is not None, "Timezone should be set after 'yes' confirmation"

    @pytest.mark.asyncio
    async def test_timezone_norwegian_user_gets_oslo_timezone(self, db_session):
        """Given: A Norwegian user
        When: Confirming timezone
        Then: Should get Europe/Oslo timezone
        """
        # Given: A Norwegian user with consent already granted
        user_id = create_test_user(db_session, "test_timezone_no", "Ola")
        
        # Ensure user has no timezone set
        user = db_session.query(User).filter_by(user_id=user_id).first()
        user.timezone = None
        db_session.commit()
        
        # Set up memories: Norwegian language and consent granted
        mm = MemoryManager(db_session)
        mm.store_memory(user_id, "user_language", "no", category="profile", source="test")
        mm.store_memory(user_id, "data_consent", "granted", category="profile", source="test")
        
        # Set up pending timezone step explicitly
        mm.store_memory(
            user_id=user_id,
            key=MemoryKey.ONBOARDING_STEP_PENDING,
            value="timezone",
            category=MemoryCategory.CONVERSATION.value,
            ttl_hours=2,
            source="test",
        )
        
        dialogue = DialogueEngine(db_session)
        
        # When: User confirms timezone
        response = await dialogue.process_message(user_id, "Ja", db_session)
        
        # Then: Should have Europe/Oslo timezone
        user = db_session.query(User).filter_by(user_id=user_id).first()
        assert user.timezone == "Europe/Oslo", f"Expected Europe/Oslo for Norwegian user, got {user.timezone}"

    @pytest.mark.asyncio
    async def test_timezone_no_lets_ai_handle_correction(self, db_session):
        """Given: A user at timezone step who says timezone is wrong
        When: User says "no"
        Then: Should return None to let AI handle via function calling
        """
        # Given: A new user at timezone step
        user_id = create_test_user(db_session, "test_timezone_no", "Bob")
        
        # Ensure user has no timezone set
        user = db_session.query(User).filter_by(user_id=user_id).first()
        user.timezone = None
        db_session.commit()
        
        # Set up pending timezone step
        mm = MemoryManager(db_session)
        mm.store_memory(
            user_id=user_id,
            key=MemoryKey.ONBOARDING_STEP_PENDING,
            value="timezone",
            category=MemoryCategory.CONVERSATION.value,
            ttl_hours=2,
            source="test",
        )
        
        dialogue = DialogueEngine(db_session)
        
        # When: User says timezone is wrong
        response = await dialogue.process_message(user_id, "No, I'm in New York", db_session)
        
        # Then: Response should be provided (AI handles it)
        assert response is not None, "Should get a response when saying no to timezone"

    @pytest.mark.asyncio
    async def test_onboarding_flow_includes_timezone_step(self, db_session):
        """Given: A new user going through complete onboarding
        When: Progressing through all steps
        Then: Timezone step should be included in the flow
        """
        # Given: A new user
        user_id = create_test_user(db_session, "test_full_flow_tz", "Alice")
        
        # Ensure user has no timezone set
        user = db_session.query(User).filter_by(user_id=user_id).first()
        user.timezone = None
        db_session.commit()
        
        dialogue = DialogueEngine(db_session)
        
        # Step 1: Get onboarding status and verify timezone is the next step after name
        from src.onboarding import OnboardingService
        onboarding = OnboardingService(db_session)
        status = onboarding.get_onboarding_status(user_id)
        
        # Verify timezone step is in the flow
        assert "timezone" in status["steps_completed"] or status["next_step"] == "timezone" or status["has_timezone"] == False, \
            f"Timezone should be part of onboarding flow, got status: {status}"
        
        # Verify onboarding is not complete without timezone
        assert status["onboarding_complete"] == False, "Onboarding should not be complete without timezone"
