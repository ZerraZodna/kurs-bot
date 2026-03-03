"""
End-to-end tests for onboarding flow.

Migrated from tests/test_onboarding_e2e.py to use new test fixtures.
"""

import pytest
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.memories import MemoryManager
from src.lessons.state import set_current_lesson
from src.scheduler.core import SchedulerService
from src.scheduler.memory_helpers import get_pending_confirmation


@pytest.mark.asyncio
async def test_onboarding_reported_current_lesson_triggers_confirmation_on_schedule_execution(db_session, test_user):
    """Given: A user who reported being on lesson 8 during onboarding
    When: The scheduled daily task is executed
    Then: Should trigger a confirmation prompt for lesson 8."""
    user_id = test_user.user_id

    mm = MemoryManager(db_session)
    # User reported they are on lesson 8 during onboarding
    set_current_lesson(mm, user_id, 8)

    # Create a daily schedule for the user (lesson_id left None to use current_lesson)
    schedule = SchedulerService.create_daily_schedule(user_id=user_id, lesson_id=None, time_str="09:00", session=db_session)

    # Simulate execution of the scheduled task (no DB mutations)
    messages = SchedulerService.execute_scheduled_task(schedule.schedule_id, simulate=True, session=db_session)

    # Expect at least one message (the confirmation prompt)
    assert messages is not None
    combined = "\n\n".join(messages) if isinstance(messages, list) else str(messages)
    assert "mentioned lesson" in combined.lower() or "nevnte leksjon" in combined.lower()

    # Verify pending confirmation persisted
    pending = get_pending_confirmation(mm, user_id)
    assert pending is not None, "Expected a pending confirmation to be stored"
    assert int(pending.get("lesson_id")) == 8
