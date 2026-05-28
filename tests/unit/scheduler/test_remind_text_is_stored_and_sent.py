"""
Migrated tests for remind text storage and sending.
 migrated from tests/test_remind_text_is_stored_and_sent.py
"""

from datetime import datetime, timedelta, UTC

import pytest

from src.functions.executor import get_function_executor
from src.models.database import Schedule


@pytest.mark.asyncio
async def test_remind_me_creates_one_time_with_correct_message(db_session):
    """Given: A user who wants to create a one-time reminder
    When: The function executor creates the schedule
    Then: The schedule is created with the correct message stored in custom_message
    """
    from tests.fixtures.users import make_ready_user

    # Given: Create a ready user with onboarding completed
    user_id = make_ready_user(db_session, external_id="remind_test_user", first_name="Remind")

    # When: Build a schedule_spec like an assistant intent would provide
    run_at = (datetime.now(UTC) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

    # When: Use FunctionExecutor to create one-time reminder
    executor = get_function_executor()
    context = {
        "user_id": user_id,
        "session": db_session,
        "memory_manager": None,
    }

    result = await executor.execute_single(
        "create_one_time_reminder",
        {
            "run_at": run_at.isoformat(),
            "message": "Remind me to go out with the garbage at 12:00",
        },
        context,
    )

    # Then: Operation should succeed
    assert result.success is True
    assert result.result.get("ok") is True

    # Then: Verify a one-time schedule row exists
    schedules = db_session.query(Schedule).filter_by(user_id=user_id).all()
    one_time = [s for s in schedules if s.schedule_type and s.schedule_type.startswith("one_time")]
    assert len(one_time) == 1

    # Then: Verify the stored schedule message matches the provided text
    assert one_time[0].custom_message == "Remind me to go out with the garbage at 12:00"
