import pytest
import asyncio
from pathlib import Path
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal
from tests.utils import create_test_user
from src.memories import MemoryManager
from src.scheduler.lesson_state import (
    set_current_lesson,
    get_current_lesson,
    get_last_sent_lesson_id,
    set_last_sent_lesson_id,
)
from src.services.dialogue.command_handlers import handle_debug_next_day
from src.services.dialogue.lesson_advance import maybe_send_next_lesson
from src.services.dialogue.reminder_handler import handle_lesson_confirmation
from src.services.prompt_builder import PromptBuilder
from src.scheduler.memory_utils import get_pending_confirmation, set_pending_confirmation
from src.scheduler.lesson_state_flow import determine_lesson_action
from src.models.database import Lesson


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


def test_gap_triggers_confirmation_after_two_days():
    db = SessionLocal()
    user_id = create_test_user(db, "test_gap_user")
    mm = MemoryManager(db)

    # Seed last sent lesson
    set_last_sent_lesson_id(mm, user_id, 6)

    # Simulate two days later
    future_date = (datetime.now(timezone.utc) + timedelta(days=2)).date()
    decision = determine_lesson_action(mm, user_id, today=future_date, max_gap_without_confirmation=1)

    assert decision["action"] == "confirm"
    assert decision["confirmation_lesson_id"] == 6
    assert decision["next_lesson_id"] == 7

    db.close()


@pytest.mark.asyncio
async def test_confirmation_accepts_rich_progress_update_and_syncs_lesson_state():
    db = SessionLocal()
    user_id = create_test_user(db, "test_rich_confirmation_user")
    mm = MemoryManager(db)

    # Seed lessons so the handler can deliver a concrete lesson response.
    db.add(Lesson(lesson_id=12, title="L12", content="Lesson 12 content"))
    db.commit()

    # Bot is waiting for confirmation around an older lesson.
    set_pending_confirmation(mm, user_id, lesson_id=6, next_lesson_id=7)

    class _OnboardingStub:
        @staticmethod
        def detect_commitment_keywords(_: str) -> bool:
            return False

    async def _translate_identity(text: str, _language: str) -> str:
        return text

    async def _format_lesson(lesson, _language: str) -> str:
        return f"Lesson {lesson.lesson_id}: {lesson.title}"

    response = await handle_lesson_confirmation(
        user_id=user_id,
        text="Well, I finished lesson 6 two days ago, now I am on lesson 12.",
        session=db,
        memory_manager=mm,
        onboarding_service=_OnboardingStub(),
        translate_fn=_translate_identity,
        get_language_fn=lambda _uid: "en",
        format_lesson_fn=_format_lesson,
    )

    assert response is not None
    assert "Lesson 12" in response

    pending = get_pending_confirmation(mm, user_id)
    assert pending is None, "Expected pending confirmation to be resolved"
    assert get_current_lesson(mm, user_id) == 12
    assert get_last_sent_lesson_id(mm, user_id) == 12

    completed = mm.get_memory(user_id, "lesson_completed")
    assert completed, "Expected extracted completion fact to be stored"
    # Rich progress update should mark the most recently completed lesson (current - 1)
    assert str(completed[0].get("value")) == "11"

    db.close()
