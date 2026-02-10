import pytest
from src.models.database import SessionLocal, User, init_db
from tests.utils import create_test_user
from src.services.trigger_dispatcher import TriggerDispatcher
from src.services.scheduler import SchedulerService


# Use shared test helper


def test_update_schedule_infers_daily_change():
    db = SessionLocal()
    try:
        init_db()
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
        # cron expression minute hour for 10:15 -> '15 10 * * *'
        assert sched.cron_expression.startswith("15 10") or (sched.next_send_time and sched.next_send_time.hour == 10)

    finally:
        db.close()
