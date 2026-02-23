import pytest
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal
from tests.utils import create_test_user
from src.memories import MemoryManager
from src.lessons.state import set_current_lesson
from src.scheduler.core import SchedulerService
from src.memories.scheduler_helpers import get_pending_confirmation


@pytest.mark.asyncio
async def test_onboarding_reported_current_lesson_triggers_confirmation_on_schedule_execution():
    db = SessionLocal()
    user_id = create_test_user(db, "e2e_onboard_user")

    mm = MemoryManager(db)
    # User reported they are on lesson 8 during onboarding
    set_current_lesson(mm, user_id, 8)

    # Create a daily schedule for the user (lesson_id left None to use current_lesson)
    schedule = SchedulerService.create_daily_schedule(user_id=user_id, lesson_id=None, time_str="09:00", session=db)

    # Simulate execution of the scheduled task (no DB mutations)
    messages = SchedulerService.execute_scheduled_task(schedule.schedule_id, simulate=True, session=db)

    # Expect at least one message (the confirmation prompt)
    assert messages is not None
    combined = "\n\n".join(messages) if isinstance(messages, list) else str(messages)
    assert "did you complete" in combined.lower() or "fullførte du" in combined.lower()

    # Verify pending confirmation persisted
    pending = get_pending_confirmation(mm, user_id)
    assert pending is not None, "Expected a pending confirmation to be stored"
    assert int(pending.get("lesson_id")) == 8

    db.close()
