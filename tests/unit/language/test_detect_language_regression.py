"""Regression tests for language detection.

Migrated from tests/test_detect_language_regression.py to use new test fixtures.
"""

from datetime import datetime, timezone

import pytest

from src.models.database import User
from src.services.dialogue_engine import DialogueEngine


class TestDetectLanguageRegression:
    """Regression tests for language detection misclassification."""

    @pytest.mark.asyncio
    async def test_english_message_triggers_german_detection(self, db_session):
        """Given: A user
        When: Sending English message "When is my reminder"
        Then: Should detect and store English, not German (regression test)
        """
        # Given: A user
        user = User(
            external_id="test_detect_language_regression",
            channel="test",
            first_name="Test",
            opted_in=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        db_session.commit()
        
        dialogue = DialogueEngine(db_session)
        
        # When: Processing the problematic English message
        problematic_msg = "When is my reminder"
        await dialogue.process_message(user.user_id, problematic_msg, db_session)
        
        # Then: Should detect English, not German
        lang_memories = dialogue.memory_manager.get_memory(user.user_id, "user_language")
        assert lang_memories, "No user_language memory was stored"
        assert any(m["value"].lower().startswith("en") for m in lang_memories), (
            "Expected English language memory to have been stored (regression),"
            f" but got: {[m['value'] for m in lang_memories]}"
        )

