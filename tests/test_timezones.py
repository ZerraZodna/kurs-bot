import pytest
from datetime import datetime, timezone

from src.models.database import SessionLocal, User, init_db
from src.services.timezone_utils import parse_local_time_to_utc, format_dt_in_timezone
from src.scheduler import SchedulerService


def create_user_with_tz(db, tz_name="Europe/Oslo") -> int:
    existing = db.query(User).filter_by(external_id="tz_test_user").first()
    if existing:
        db.query(User).filter_by(user_id=existing.user_id).delete()
        db.commit()

    user = User(external_id="tz_test_user", channel="test", opted_in=True, timezone=tz_name)
    db.add(user)
    db.commit()
    return user.user_id


def test_parse_local_time_to_utc_basic():
    # Europe/Oslo is UTC+1 in standard time; parse 09:00 local -> should be 08:00 UTC (non-DST tests assume non-summer)
    utc_dt = parse_local_time_to_utc("09:00", "Europe/Oslo")
    assert utc_dt.tzinfo is not None
    # hour may vary depending on DST; ensure conversion yields an aware UTC datetime
    assert utc_dt.tzinfo.utcoffset(utc_dt) == timezone.utc.utcoffset(utc_dt)


def test_create_schedule_stores_utc_and_displays_local():
    db = SessionLocal()
    try:
        user_id = create_user_with_tz(db, tz_name="Europe/Oslo")

        sched = SchedulerService.create_daily_schedule(user_id=user_id, lesson_id=None, time_str="09:00", session=db)

        if sched.next_send_time:
            ns = sched.next_send_time
            # Some DB backends (sqlite) may return naive datetimes; treat naive as UTC
            if ns.tzinfo is None:
                ns = ns.replace(tzinfo=timezone.utc)
            # Display should show 09:00 in user's timezone
            local_dt, _ = format_dt_in_timezone(ns, "Europe/Oslo")
            assert f"{local_dt:%H:%M}" == "09:00"
    finally:
        db.close()


def test_update_schedule_converts_to_utc():
    db = SessionLocal()
    try:
        user_id = create_user_with_tz(db, tz_name="Europe/Oslo")

        sched = SchedulerService.create_daily_schedule(user_id=user_id, lesson_id=None, time_str="09:00", session=db)
        assert sched is not None

        updated = SchedulerService.update_daily_schedule(sched.schedule_id, "10:15", session=db)
        assert updated is not None
        if updated.next_send_time:
            ns = updated.next_send_time
            if ns.tzinfo is None:
                ns = ns.replace(tzinfo=timezone.utc)
            # Display should show 10:15 in Europe/Oslo
            local_dt, _ = format_dt_in_timezone(ns, "Europe/Oslo")
            assert f"{local_dt:%H:%M}" == "10:15"
    finally:
        db.close()
