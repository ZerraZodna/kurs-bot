"""
Test that user language override commands update the stored `user_language` memory.

Steps:
1. Create a new test user
2. Seed `user_language` memory with `fr`
3. Send message: "Set language to English"
4. Verify `user_language` memory becomes `en`
"""

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal
from src.services.memory_manager import MemoryManager
from src.services.dialogue_engine import DialogueEngine
from tests.utils import make_ready_user


@pytest.mark.asyncio
async def test_set_language_to_english_overrides_french():
    db = SessionLocal()
    try:
        user_id = make_ready_user(db, external_id="test_user_lang", first_name="John-test")
        mm = MemoryManager(db)

        # User issues override command via full pipeline
        dialogue = DialogueEngine(db)
        # First populate some messages for the user
        msg = "I really like you"
        response = await dialogue.process_message(user_id, msg, db)
        print(response)

        # Seed existing language preference as French (bug)
        mm.store_memory(user_id=user_id, key="user_language", value="fr", confidence=0.9, source="test", category="preference")

        msg2 = "Set language to English"
        print(msg2)
        response = await dialogue.process_message(user_id, msg2, db)
        print(response)

        # Fetch stored memories and assert language changed to 'en'
        lang_memories = mm.get_memory(user_id, "user_language")
        assert lang_memories, "No user_language memory stored after override"
        assert any(m["value"].lower().startswith("en") for m in lang_memories), (
            f"Expected 'en' to be stored after message '{msg}', got: {[m['value'] for m in lang_memories]}"
        )

    finally:
        db.close()
