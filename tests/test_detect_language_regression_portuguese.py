"""
Regression test reproducing Portuguese misclassification observed in logs.

This test pre-populates an existing `user_language` value of German,
then runs `detect_and_store_language` on the message that was logged
to have caused a switch to Portuguese. The test asserts that the
detector stored Portuguese, reproducing the bug.
"""

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal
from src.services.memory_manager import MemoryManager
from src.services.language.language_service import detect_and_store_language
from tests.utils import create_test_user


@pytest.mark.asyncio
async def test_portuguese_detection_overwrites_german():
    db = SessionLocal()
    try:
        user_id = create_test_user(db, external_id="regress_lang_user_pt")
        mm = MemoryManager(db)

        # Pre-populate an existing language preference (German) with moderate confidence
        # so detection may overwrite if new evidence is stronger.
        mm.store_memory(user_id=user_id, key="user_language", value="en", confidence=0.7, source="test", category="preference")

        # Problematic message observed in logs
        problematic_msg = "Yea do a search"

        # Run detection
        result = await detect_and_store_language(mm, user_id, problematic_msg)

        # Fetch stored memory and assert Portuguese was stored
        lang_memories = mm.get_memory(user_id, "user_language")
        assert lang_memories, "No user_language memory stored"
        assert any(m["value"].lower().startswith("en") for m in lang_memories), (
            f"Expected English to be stored for message '{problematic_msg}', got: {[m['value'] for m in lang_memories]}"
        )

    finally:
        db.close()
