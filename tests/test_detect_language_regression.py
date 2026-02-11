"""
Regression tests for language detection misclassification.

These tests replay real user inputs observed in production that led to
incorrect `user_language` memories (Portuguese/German). They are
intended to reproduce the regression so we can design a robust fix.
"""

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal
from src.services.dialogue_engine import DialogueEngine
from tests.utils import create_test_user
from src.models.database import MessageLog


@pytest.mark.asyncio
async def test_english_message_triggers_german_detection():
    """Replays the English message that previously produced a German memory.

    This test will fail if the current detection implementation still
    misclassifies the input. It intentionally avoids heavy mocking so
    it exercises the real detection path used by `process_message`.
    """
    db = SessionLocal()
    try:
        user_id = create_test_user(db, external_id="regress_lang_user_de")
        dialogue = DialogueEngine(db)

        # The message observed in the logs immediately before a German
        # `user_language` memory was created for user 7.
        problematic_msg = "When is my reminder"

        # Process the message using the real pipeline
        await dialogue.process_message(user_id, problematic_msg, db)

        lang_memories = dialogue.memory_manager.get_memory(user_id, "user_language")
        # Diagnostic dump for debugging: show stored memories and message logs
        print("--- DEBUG: user_language memories ->", lang_memories)
        msgs = db.query(MessageLog).filter(MessageLog.user_id == user_id).order_by(MessageLog.created_at).all()
        print("--- DEBUG: MessageLog rows:")
        for m in msgs:
            print(f"  {m.direction} | {m.created_at} | {m.content}")
        # The regression is that the system stored German for this input.
        assert lang_memories, "No user_language memory was stored"
        # If this currently misbehaves in your environment, this assertion will show it.
        assert any(m["value"].lower().startswith("en") for m in lang_memories), (
            "Expected English language memory to have been stored (regression),"
            " but it was not."
        )

    finally:
        db.close()
