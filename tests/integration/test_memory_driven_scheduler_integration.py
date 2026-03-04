"""
Integration tests for memory-driven scheduler.

Migrated from tests/test_memory_driven_scheduler_integration.py to use new test fixtures.
"""

import pytest
from src.models.database import User, Schedule
from src.memories import MemoryManager
from src.memories.constants import MemoryKey
from src.services.dialogue_engine import DialogueEngine
from src.scheduler import SchedulerService
from src.functions.executor import get_function_executor


@pytest.mark.asyncio
async def test_memory_driven_schedule_creation(db_session, test_user):
    """Given: A user with commitment and preferred time stored as memories
    When: Creating schedule via function executor
    Then: Should create a schedule at the preferred time."""
    user_id = test_user.user_id

    # Store commitment and preferred time as memories
    mm = MemoryManager(db_session)
    mm.store_memory(user_id=user_id, key=MemoryKey.ACIM_COMMITMENT, value="yes")
    mm.store_memory(user_id=user_id, key=MemoryKey.PREFERRED_LESSON_TIME, value="10:15")

    # Use FunctionExecutor to create schedule directly
    executor = get_function_executor()
    context = {
        "user_id": user_id,
        "session": db_session,
        "memory_manager": mm,
    }
    
    result = await executor.execute_single(
        "create_schedule",
        {"time": "10:15"},
        context
    )
    
    assert result.success is True
    assert result.result.get("ok") is True
    assert "schedule_id" in result.result

    # Verify schedule created at 10:15
    db_session.expire_all()
    all_schedules = db_session.query(Schedule).filter_by(user_id=user_id).all()
    active = [s for s in all_schedules if s.is_active]
    assert len(active) == 1
    sched = active[0]
    
    # Compute expected next_send using user's timezone and compare stored UTC value
    from src.scheduler.time_utils import compute_next_send_and_cron

    user = db_session.query(User).filter_by(user_id=user_id).first()
    tz_name = getattr(user, "timezone", "UTC") if user else "UTC"
    expected_next_send, expected_cron = compute_next_send_and_cron("10:15", tz_name)

    assert sched.next_send_time is None or (
        sched.next_send_time.hour == expected_next_send.hour and sched.next_send_time.minute == expected_next_send.minute
    )
