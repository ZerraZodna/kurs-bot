"""
Migrated tests for one-time schedule creation.
 migrated from tests/test_one_time_does_not_modify_daily.py
"""
from datetime import datetime, timedelta, timezone

from src.models.database import Schedule, SessionLocal
from src.scheduler import SchedulerService


def test_one_time_creation_does_not_modify_daily():
    """Given: A user with a daily schedule
    When: A one-time reminder is created
    Then: The daily schedule remains unchanged
    """
    db = SessionLocal()
    try:
        from tests.fixtures.users import make_ready_user

        # Given: Create a ready user with onboarding completed
        user_id = make_ready_user(db, external_id="one_time_test", first_name="One")

        # Given: Create a daily schedule
        daily = SchedulerService.create_daily_schedule(user_id=user_id, lesson_id=None, time_str="08:00", session=db)

        # When: Create a one-time reminder for the same user
        run_at = datetime.now(timezone.utc) + timedelta(hours=1)
        one = SchedulerService.create_one_time_schedule(user_id=user_id, run_at=run_at, message="One-time reminder", session=db)

        # Then: Reload schedules from DB and assert both exist and daily was not modified
        schedules = db.query(Schedule).filter_by(user_id=user_id).all()
        daily_schedules = [s for s in schedules if s.schedule_type and s.schedule_type.startswith("daily")]
        one_time_schedules = [s for s in schedules if s.schedule_type and s.schedule_type.startswith("one_time")]

        assert len(daily_schedules) == 1
        assert daily_schedules[0].is_active
        assert len(one_time_schedules) == 1
        assert one_time_schedules[0].is_active

    finally:
        db.close()

