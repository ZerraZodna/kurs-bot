"""Unit tests for language detection with short messages.

Migrated from tests/test_language_detection_short_messages.py to use new test fixtures.
"""

from datetime import datetime, timezone

import pytest

from src.models.database import User
from src.services.dialogue_engine import DialogueEngine


class TestLanguageDetectionShortMessages:
    """Tests for language detection behavior with short messages."""

    @pytest.mark.asyncio
    async def test_short_message_does_not_overwrite_detected_language(self, db_session):
        """Given: A user with detected Norwegian language
        When: Sending short English reply (<=4 words)
        Then: Language should remain Norwegian
        """
        # Given: A user
        user = User(
            external_id="test_language_short_messages",
            channel="test",
            first_name="Test",
            opted_in=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        db_session.commit()

        dialogue = DialogueEngine(db_session)

        # When: First sending Norwegian message to set language
        norwegian_msg = "Hei! Jeg heter Johannes"
        await dialogue.process_message(user.user_id, norwegian_msg, db_session)

        # Then: Language should be stored as Norwegian
        lang_memories = dialogue.memory_manager.get_memory(user.user_id, "user_language")
        assert lang_memories and lang_memories[0]["value"].lower().startswith("no")

        # When: Sending short English reply
        short_reply = "Yes, sounds good"
        await dialogue.process_message(user.user_id, short_reply, db_session)

        # Then: Language should remain Norwegian
        lang_memories_after = dialogue.memory_manager.get_memory(user.user_id, "user_language")
        assert lang_memories_after and lang_memories_after[0]["value"].lower().startswith("no")
