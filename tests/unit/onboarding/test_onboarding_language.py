"""Unit tests for onboarding language detection.

Migrated from tests/test_onboarding_language.py to use new test fixtures.
"""

import pytest
from datetime import datetime, timezone

from src.models.database import User, Memory
from src.services.dialogue_engine import DialogueEngine


class TestOnboardingLanguage:
    """Tests for onboarding language detection."""

    @pytest.mark.asyncio
    async def test_onboarding_uses_detected_language_for_prompts(self, db_session):
        """Given: A new user
        When: Sending Norwegian greeting 'Hei'
        Then: Should detect Norwegian and respond with Norwegian prompts
        """
        # Given: A new user
        user = User(
            external_id="test_onboarding_language_detect",
            channel="test",
            first_name=None,
            opted_in=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        db_session.commit()
        
        dialogue = DialogueEngine(db_session)
        
        # When: Sending Norwegian greeting
        resp = await dialogue.process_message(user.user_id, "Hei", db_session)
        
        # Then: Memory should be created with Norwegian
        mems = db_session.query(Memory).filter_by(user_id=user.user_id, key="user_language").all()
        assert len(mems) > 0, "Expected a user_language memory to be stored"
        assert any(m.value == "no" for m in mems), f"Expected stored language 'no', got {[m.value for m in mems]}"
        
        # And: The onboarding response should be in Norwegian
        assert (
            "Hva heter" in resp or "Velkommen" in resp or "Før vi fortsetter" in resp
        ), f"Onboarding response was not Norwegian: {resp}"

