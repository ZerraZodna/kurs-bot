"""
Unit tests for TriggerDispatcher update functionality.

Migrated from tests/test_trigger_dispatcher_update.py to use new test fixtures.
"""

import pytest
from src.models.database import User
from src.triggers.trigger_dispatcher import TriggerDispatcher
from src.scheduler import SchedulerService


class TestTriggerDispatcherUpdate:
    """Test suite for TriggerDispatcher update functionality."""

    def test_update_schedule_infers_daily_change(self, db_session, test_user):
        """Given: A user with an existing daily schedule at 09:00
        When: Dispatching an update_schedule trigger to change time to 10:15
        Then: Should update the schedule to the new time."""
        # Given: create initial daily schedule
        user_id = test_user.user_id
        SchedulerService.create_daily_schedule(user_id=user_id, lesson_id=None, time_str="09:00", session=db_session)

        dispatcher = TriggerDispatcher(db=db_session)

        match = {"trigger_id": 1, "name": "update_schedule", "action_type": "update_schedule"}
        context = {"user_id": user_id, "original_text": "Change it to 10:15"}

        res = dispatcher.dispatch(match, context)
        assert res.get("ok") is True

        schedules = SchedulerService.get_user_schedules(user_id)
        active = [s for s in schedules if s.is_active]
        assert len(active) == 1
        sched = active[0]
        # Compute expected next_send using user's timezone and compare stored UTC value
        from src.scheduler.time_utils import compute_next_send_and_cron

        user = db_session.query(User).filter_by(user_id=user_id).first()
        tz_name = getattr(user, "timezone", "UTC") if user else "UTC"
        expected_next_send, expected_cron = compute_next_send_and_cron("10:15", tz_name)

        assert sched.cron_expression.startswith(f"{expected_next_send.minute} {expected_next_send.hour}") or (
            sched.next_send_time and sched.next_send_time.hour == expected_next_send.hour
        )

