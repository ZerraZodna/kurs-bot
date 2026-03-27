"""Unit tests for language override command.

Migrated from tests/test_language_override_set_command.py to use new test fixtures.
"""

from datetime import datetime, timezone

import pytest

from src.memories import MemoryManager
from src.models.database import User
from src.services.dialogue_engine import DialogueEngine


class TestLanguageOverrideSetCommand:
    """Tests for language override set command."""

    @pytest.mark.asyncio
    async def test_set_language_to_english_overrides_french(self, db_session):
        """Given: A user with French language preference
        When: Sending "Set language to English" command
        Then: Language should change to English
        """
        # Given: A ready user with French language preference
        user = User(
            external_id="test_language_override",
            channel="test",
            first_name="John",
            opted_in=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        db_session.commit()

        mm = MemoryManager(db_session)
        mm.store_memory(user.user_id, "first_name", "John", category="profile", source="test")
        mm.store_memory(user.user_id, "data_consent", "yes", category="profile", source="test")

        # Seed existing language preference as French
        mm.store_memory(user_id=user.user_id, key="user_language", value="fr", source="test", category="preference")

        dialogue = DialogueEngine(db_session)

        # When: User issues override command
        msg = "Set language to English"
        response = await dialogue.process_message(user.user_id, msg, db_session)

        # Then: Language should change to 'en'
        lang_memories = mm.get_memory(user.user_id, "user_language")
        assert lang_memories, "No user_language memory stored after override"
        assert any(
            m["value"].lower().startswith("en") for m in lang_memories
        ), f"Expected 'en' to be stored after message '{msg}', got: {[m['value'] for m in lang_memories]}"
