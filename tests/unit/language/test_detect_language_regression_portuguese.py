"""Regression tests for Portuguese language detection.

Migrated from tests/test_detect_language_regression_portuguese.py to use new test fixtures.
"""

from datetime import datetime, timezone

import pytest

from src.language.language_service import detect_and_store_language
from src.memories import MemoryManager
from src.models.database import User


class TestDetectLanguageRegressionPortuguese:
    """Regression tests for Portuguese language detection."""

    @pytest.mark.asyncio
    async def test_portuguese_detection_overwrites_german(self, db_session):
        """Given: A user with existing German language preference
        When: Sending message "Yea do a search"
        Then: Should detect and store English (not Portuguese)
        """
        # Given: A user with existing language preference
        user = User(
            external_id="test_detect_language_portuguese",
            channel="test",
            first_name="Test",
            opted_in=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        db_session.commit()

        mm = MemoryManager(db_session)

        # Pre-populate an existing language preference (German/English)
        mm.store_memory(user_id=user.user_id, key="user_language", value="en", source="test", category="preference")

        # When: Running detection on problematic message
        problematic_msg = "Yea do a search"
        result = await detect_and_store_language(mm, user.user_id, problematic_msg)

        # Then: Should store English, not Portuguese
        lang_memories = mm.get_memory(user.user_id, "user_language")
        assert lang_memories, "No user_language memory stored"
        assert any(
            m["value"].lower().startswith("en") for m in lang_memories
        ), f"Expected English to be stored for message '{problematic_msg}', got: {[m['value'] for m in lang_memories]}"
