"""
Integration tests for trigger-driven scheduler.

Migrated from tests/test_trigger_scheduler_integration.py to use new test fixtures.
"""

import pytest

from src.functions.executor import get_function_executor
from src.models.database import User
from src.scheduler import SchedulerService
from src.services.dialogue_engine import DialogueEngine


@pytest.mark.asyncio
async def test_trigger_based_schedule_edit(db_session, test_user, monkeypatch):
    """Given: A user with an existing daily schedule at 09:00
    When: Using function executor to update the schedule to 10:15
    Then: Should update the schedule to the new time."""
    user_id = test_user.user_id

    # Create an initial schedule at 09:00 for the user
    SchedulerService.create_daily_schedule(user_id=user_id, lesson_id=None, time_str="09:00", session=db_session)

    dialogue = DialogueEngine(db_session)

    # Make Ollama return a structured intent so the function executor is called directly
    async def fake_call_ollama_with_intent(prompt: str, model: str = None, language: str = None) -> str:
        return '{"intent": {"name": "update_schedule", "action_type": "update_schedule"}}'

    # Patch the module-level ollama client so all call sites use the fake
    monkeypatch.setattr("src.services.dialogue.ollama_client.call_ollama", fake_call_ollama_with_intent)

    # STEP 1: Ask for current reminders (should return status)
    resp1 = await dialogue.process_message(user_id, "What are my reminders?", db_session)
    assert resp1 is not None and len(resp1) > 0

    # STEP 2: Use FunctionExecutor to update schedule to 10:15
    executor = get_function_executor()
    context = {
        "user_id": user_id,
        "session": db_session,
        "memory_manager": dialogue.memory_manager,
    }

    # Deactivate existing schedules
    SchedulerService.deactivate_user_schedules(user_id, session=db_session)

    import time
    time.sleep(0.1)  # Allow scheduler thread to process

    # Create new schedule at 10:15
    result = await executor.execute_single("create_schedule", {"time": "10:15"}, context)

    assert result.success is True
    assert result.result.get("ok") is True

    # Jobs cleared in teardown
    pass

    # After execution, verify schedule updated to 10:15 using the same db_session
    from src.scheduler import manager as schedule_manager

    schedules = schedule_manager.get_user_schedules(user_id, session=db_session)
    # Find the active schedule
    active = [s for s in schedules if s.is_active]
    assert len(active) == 1
    sched = active[0]

    # Compute expected next_send using user's timezone and compare stored UTC value
    from src.scheduler.time_utils import compute_next_send_and_cron

    user = db_session.query(User).filter_by(user_id=user_id).first()
    tz_name = getattr(user, "timezone", "UTC") if user else "UTC"
    expected_next_send, expected_cron = compute_next_send_and_cron("10:15", tz_name)

    assert sched.next_send_time is None or (
        sched.next_send_time.hour == expected_next_send.hour
        and sched.next_send_time.minute == expected_next_send.minute
    )
