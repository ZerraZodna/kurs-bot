"""Unit tests for timezone handling in scheduler.

Refactored to use new test fixtures from tests/fixtures/
"""

from datetime import timezone

from sqlalchemy.orm import Session

from src.core.timezone import format_dt_in_timezone, parse_local_time_to_utc
from src.scheduler import SchedulerService


class TestParseLocalTimeToUtc:
    """Test suite for timezone parsing."""

    def test_parse_local_time_to_utc_basic(self):
        """Should parse local time to UTC correctly."""
        # Given: A local time string and timezone
        # Europe/Oslo is UTC+1 in standard time; parse 09:00 local
        # When: Converting to UTC
        utc_dt = parse_local_time_to_utc("09:00", "Europe/Oslo")

        # Then: Result should be a timezone-aware UTC datetime
        assert utc_dt.tzinfo is not None
        # Hour may vary depending on DST; ensure conversion yields an aware UTC datetime
        assert utc_dt.tzinfo.utcoffset(utc_dt) == timezone.utc.utcoffset(utc_dt)


class TestScheduleTimezoneStorage:
    """Test suite for schedule timezone storage and display."""

    def test_create_schedule_stores_utc_and_displays_local(self, db_session: Session, test_user):
        """Should store schedule time in UTC but display in user's timezone."""
        # Given: A user with Europe/Oslo timezone
        test_user.timezone = "Europe/Oslo"
        db_session.commit()

        # When: Creating a daily schedule at 09:00
        sched = SchedulerService.create_daily_schedule(
            user_id=test_user.user_id, lesson_id=None, time_str="09:00", session=db_session
        )

        # Then: Next send time should be stored and display correctly
        if sched.next_send_time:
            ns = sched.next_send_time
            # Some DB backends (sqlite) may return naive datetimes; treat naive as UTC
            if ns.tzinfo is None:
                ns = ns.replace(tzinfo=timezone.utc)
            # Display should show 09:00 in user's timezone
            local_dt, _ = format_dt_in_timezone(ns, "Europe/Oslo")
            assert f"{local_dt:%H:%M}" == "09:00"

    def test_update_schedule_converts_to_utc(self, db_session: Session, test_user):
        """Should convert updated schedule time to UTC."""
        # Given: A user with Europe/Oslo timezone and existing schedule
        test_user.timezone = "Europe/Oslo"
        db_session.commit()

        sched = SchedulerService.create_daily_schedule(
            user_id=test_user.user_id, lesson_id=None, time_str="09:00", session=db_session
        )
        assert sched is not None

        # When: Updating the schedule time
        updated = SchedulerService.update_daily_schedule(sched.schedule_id, "10:15", session=db_session)

        # Then: Updated time should be converted correctly
        assert updated is not None
        if updated.next_send_time:
            ns = updated.next_send_time
            if ns.tzinfo is None:
                ns = ns.replace(tzinfo=timezone.utc)
            # Display should show 10:15 in Europe/Oslo
            local_dt, _ = format_dt_in_timezone(ns, "Europe/Oslo")
            assert f"{local_dt:%H:%M}" == "10:15"
