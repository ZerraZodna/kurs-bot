"""
Test that a new user sending a short greeting "Hi" is detected as English
and stored as `user_language` == 'en'.
"""

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal
from src.memories import MemoryManager
from src.services.language.language_service import detect_and_store_language
from tests.utils import create_test_user


@pytest.mark.asyncio
async def test_hi_detects_english_and_stores_en():
    db = SessionLocal()
    try:
        user_id = create_test_user(db, external_id="hi_test_user")
        mm = MemoryManager(db)

        result = await detect_and_store_language(mm, user_id, "Hi")
        print(result)

        lang_memories = mm.get_memory(user_id, "user_language")
        assert lang_memories, "No user_language memory stored"
        assert any(m["value"].lower().startswith("en") for m in lang_memories), (
            f"Expected 'en' to be stored for message 'Hi', got: {[m['value'] for m in lang_memories]}"
        )

    finally:
        db.close()
