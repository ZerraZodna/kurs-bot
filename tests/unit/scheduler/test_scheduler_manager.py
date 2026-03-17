"""Unit tests for scheduler manager.

Refactored to use new test fixtures from tests/fixtures/
"""

import datetime
from sqlalchemy.orm import Session

from src.models.database import Schedule
from src.scheduler import manager


class TestSchedulerManager:
    """Test suite for scheduler manager functions."""

    def test_create_get_update_deactivate(
        self, db_session: Session, test_user, lesson
    ):
        """Should create, get, update, and deactivate schedules."""
        # Given: A user and lesson exist in the database
        
        # When: Creating a schedule
        sched = manager.create_schedule(
            user_id=test_user.user_id,
            lesson_id=lesson.lesson_id,
            schedule_type="daily",
            cron_expression="0 9 * * *",
            next_send_time=datetime.datetime.utcnow(),
            session=db_session,
        )
        
        # Then: Schedule should be created with an ID
        assert sched.schedule_id is not None

        # When: Getting user schedules
        schedules = manager.get_user_schedules(
            test_user.user_id, active_only=True, session=db_session
        )
        
        # Then: Should return one schedule
        assert len(schedules) == 1

        # When: Updating the schedule
        updated = manager.update_schedule(
            sched.schedule_id,
            {"cron_expression": "0 10 * * *"},
            session=db_session
        )
        
        # Then: Update should succeed
        assert updated is not None
        assert updated.cron_expression == "0 10 * * *"

        # When: Deactivating the schedule
        ok = manager.deactivate_schedule(sched.schedule_id, session=db_session)
        
        # Then: Deactivation should succeed
        assert ok is True
        updated_schedule = db_session.query(Schedule).filter_by(schedule_id=sched.schedule_id).first()
        assert updated_schedule.is_active is False

    def test_find_active_daily_and_deactivate_user(
        self, db_session: Session, test_user
    ):
        """Should find active daily schedules and deactivate all user schedules."""
        # Given: A user with two schedules
        s1 = manager.create_schedule(
            user_id=test_user.user_id,
            lesson_id=None,
            schedule_type="daily",
            cron_expression="0 8 * * *",
            session=db_session
        )
        s2 = manager.create_schedule(
            user_id=test_user.user_id,
            lesson_id=None,
            schedule_type="daily",
            cron_expression="0 7 * * *",
            session=db_session
        )

        # When: Finding active daily schedule
        found = manager.find_active_daily_schedule(
            test_user.user_id, session=db_session
        )
        
        # Then: Should find an active schedule
        assert found is not None

        # When: Deactivating all user schedules
        count = manager.deactivate_user_schedules(
            test_user.user_id, session=db_session
        )
        
        # Then: Should deactivate both schedules
        assert count == 2

