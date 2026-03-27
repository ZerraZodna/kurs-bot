"""Unit tests for language detection (Hindi/English).

Migrated from tests/test_detect_language_hi.py to use new test fixtures.
"""

from datetime import datetime, timezone

import pytest

from src.language.language_service import detect_and_store_language
from src.memories import MemoryManager
from src.models.database import User


class TestDetectLanguageHi:
    """Tests for language detection (Hindi/English)."""

    @pytest.mark.asyncio
    async def test_hi_detects_english_and_stores_en(self, db_session):
        """Given: A new user
        When: Sending greeting "Hi"
        Then: Should detect and store English ('en')
        """
        # Given: A user
        user = User(
            external_id="test_detect_language_hi",
            channel="test",
            first_name="Test",
            opted_in=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        db_session.commit()

        mm = MemoryManager(db_session)

        # When: Detecting language for "Hi"
        result = await detect_and_store_language(mm, user.user_id, "Hi")

        # Then: Should store 'en' as the language
        lang_memories = mm.get_memory(user.user_id, "user_language")
        assert lang_memories, "No user_language memory stored"
        assert any(
            m["value"].lower().startswith("en") for m in lang_memories
        ), f"Expected 'en' to be stored for message 'Hi', got: {[m['value'] for m in lang_memories]}"
