import pytest
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal
from tests.utils import create_test_user
from src.memories import MemoryManager
from src.scheduler.lesson_state import set_current_lesson
from src.services.dialogue.command_handlers import handle_debug_next_day
from src.services.dialogue.lesson_advance import maybe_send_next_lesson
from src.services.prompt_builder import PromptBuilder
from src.scheduler.memory_utils import get_pending_confirmation


@pytest.mark.asyncio
async def test_next_day_triggers_confirmation_prompt():
    db = SessionLocal()
    user_id = create_test_user(db, "test_next_day_user")

    mm = MemoryManager(db)
    # Simulate onboarding where the user reported they're on lesson 8
    set_current_lesson(mm, user_id, 8)

    # Call debug next_day to advance debug offset (simulates passage of a day)
    resp = handle_debug_next_day("next_day", mm, db, user_id)
    # debug handler should at least return 'OK' when no schedules exist
    assert resp in ("OK", None) or isinstance(resp, str)

    # Now call maybe_send_next_lesson directly to see what would be auto-sent
    prompt_builder = PromptBuilder(db, mm)
    result = await maybe_send_next_lesson(
        user_id=user_id,
        text="Hi",
        session=db,
        prompt_builder=prompt_builder,
        memory_manager=mm,
        call_ollama=lambda p, m=None, language=None: asyncio.sleep(0) or "",
    )

    assert result is not None, "Expected a confirmation prompt but got None"
    assert "did you complete" in result.lower() or "fullførte du" in result.lower()

    # Verify that a pending confirmation was persisted for the user
    pending = get_pending_confirmation(mm, user_id)
    assert pending is not None, "Expected a pending confirmation to be stored"
    assert int(pending.get("lesson_id")) == 8

    db.close()
