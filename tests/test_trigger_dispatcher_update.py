import pytest
from src.models.database import SessionLocal, User, init_db
from tests.utils import create_test_user
from src.triggers.trigger_dispatcher import TriggerDispatcher
from src.scheduler import SchedulerService


# Use shared test helper


def test_update_schedule_infers_daily_change():
    db = SessionLocal()
    try:
        user_id = create_test_user(db, "trigger-dispatch-user")

        # create initial daily schedule
        SchedulerService.create_daily_schedule(user_id=user_id, lesson_id=None, time_str="09:00", session=db)

        dispatcher = TriggerDispatcher(db=db)

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
        from src.models.database import User

        user = db.query(User).filter_by(user_id=user_id).first()
        tz_name = getattr(user, "timezone", "UTC") if user else "UTC"
        expected_next_send, expected_cron = compute_next_send_and_cron("10:15", tz_name)

        assert sched.cron_expression.startswith(f"{expected_next_send.minute} {expected_next_send.hour}") or (
            sched.next_send_time and sched.next_send_time.hour == expected_next_send.hour
        )

    finally:
        db.close()
