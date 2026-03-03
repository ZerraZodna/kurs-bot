"""
Migrated tests for remind text storage and sending.
 migrated from tests/test_remind_text_is_stored_and_sent.py
"""
import json
from datetime import datetime, timezone, timedelta

import pytest

from src.models.database import SessionLocal, User, init_db, Memory, Schedule
from src.memories import MemoryManager
from src.functions.executor import get_function_executor


@pytest.mark.asyncio
async def test_remind_me_creates_one_time_with_correct_message():
    """Given: A user who wants to create a one-time reminder
    When: The function executor creates the schedule
    Then: The schedule is created with the correct message
    """
    db = SessionLocal()
    try:
        from tests.fixtures.users import make_ready_user

        # Given: Create a ready user with onboarding completed
        user_id = make_ready_user(db, external_id="remind_test_user", first_name="Remind")

        # When: Build a schedule_spec like an assistant intent would provide
        run_at = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        
        # When: Use FunctionExecutor to create one-time reminder
        executor = get_function_executor()
        context = {
            "user_id": user_id,
            "session": db,
            "memory_manager": MemoryManager(db),
        }
        
        result = await executor.execute_single(
            "create_one_time_reminder",
            {
                "run_at": run_at.isoformat(),
                "message": "Remind me to go out with the garbage at 12:00",
            },
            context
        )
        
        # Then: Operation should succeed
        assert result.success is True
        assert result.result.get("ok") is True

        # Then: Verify a one-time schedule row exists
        schedules = db.query(Schedule).filter_by(user_id=user_id).all()
        one_time = [s for s in schedules if s.schedule_type and s.schedule_type.startswith("one_time")]
        assert len(one_time) == 1

        # Then: Verify the stored schedule message in memory matches the provided text
        mm = MemoryManager(db)
        memories = mm.get_memory(user_id=user_id, key="schedule_message")
        assert memories and len(memories) >= 1
        payload = json.loads(memories[-1].get("value"))
        assert payload.get("message") == "Remind me to go out with the garbage at 12:00"

    finally:
        db.close()
