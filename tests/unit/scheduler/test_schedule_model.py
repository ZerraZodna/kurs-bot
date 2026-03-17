"""Unit tests for Schedule model.

Refactored to use new test fixtures from tests/fixtures/
"""

from sqlalchemy.orm import Session

from src.models.database import Schedule


class TestScheduleModel:
    """Test suite for Schedule model CRUD operations."""

    def test_schedule_crud(self, db_session: Session, test_user, lesson):
        """Should create, read, update, and delete schedules."""
        # Given: A user and lesson exist

        # When: Creating a schedule
        sched = Schedule(
            user_id=test_user.user_id,
            lesson_id=lesson.lesson_id,
            schedule_type="daily",
            cron_expression="0 8 * * *",
            is_active=True,
        )
        db_session.add(sched)
        db_session.commit()

        # Then: Schedule should have an ID
        assert sched.schedule_id is not None

        # When: Reading the schedule
        fetched = db_session.query(Schedule).filter_by(schedule_type="daily").first()

        # Then: Should have correct cron expression
        assert fetched.cron_expression == "0 8 * * *"

        # When: Updating the schedule
        fetched.cron_expression = "0 9 * * *"
        db_session.commit()
        updated = db_session.query(Schedule).filter_by(schedule_id=sched.schedule_id).first()

        # Then: Update should be reflected
        assert updated.cron_expression == "0 9 * * *"

        # When: Deleting the schedule
        db_session.delete(updated)
        db_session.commit()

        # Then: Schedule should no longer exist
        assert db_session.query(Schedule).filter_by(schedule_id=sched.schedule_id).first() is None
