"""
Tests for language detection behavior with short messages.

Ensures that once a user's language is stored, brief follow-up messages
of four words or fewer do not overwrite the stored language.
"""

import asyncio
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, User
from src.services.dialogue_engine import DialogueEngine
from datetime import datetime, timezone


def create_test_user(db, external_id: str = "test_lang_user") -> int:
    existing_user = db.query(User).filter_by(external_id=external_id).first()
    if existing_user:
        from src.models.database import Memory, Schedule

        db.query(Memory).filter_by(user_id=existing_user.user_id).delete()
        db.query(Schedule).filter_by(user_id=existing_user.user_id).delete()
        db.query(User).filter_by(user_id=existing_user.user_id).delete()
        db.commit()

    user = User(
        external_id=external_id,
        channel="test",
        phone_number=None,
        email=f"{external_id}@example.com",
        first_name=None,
        last_name=None,
        opted_in=True,
        created_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user.user_id


@pytest.mark.asyncio
async def test_short_message_does_not_overwrite_detected_language():
    """Existing language should remain unchanged after a short reply."""
    db = SessionLocal()
    try:
        user_id = create_test_user(db, external_id="test_lang_user_overwrite")

        dialogue = DialogueEngine(db)

        # First, send a Norwegian introduction to set language
        norwegian_msg = "Hei! Jeg heter Johannes"
        await dialogue.process_message(user_id, norwegian_msg, db)

        # Verify language was stored as Norwegian (ISO code 'no')
        lang_memories = dialogue.memory_manager.get_memory(user_id, "user_language")
        assert lang_memories and lang_memories[0]["value"].lower().startswith("no")

        # Now send a short English reply (<=4 words)
        short_reply = "Yes, sounds good"
        await dialogue.process_message(user_id, short_reply, db)

        # Language should remain Norwegian (ISO code 'no')
        lang_memories_after = dialogue.memory_manager.get_memory(user_id, "user_language")
        assert lang_memories_after and lang_memories_after[0]["value"].lower().startswith("no")

    finally:
        db.close()
