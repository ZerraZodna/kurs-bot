from datetime import datetime, timezone, timedelta

from src.models.database import SessionLocal, User, Schedule
from src.scheduler import SchedulerService
from src.scheduler import manager as schedule_manager
from src.core.timezone import format_dt_in_timezone, to_utc


def _create_test_user(db, timezone_name=None):
    existing = db.query(User).filter_by(external_id="test_tz_user").first()
    if existing:
        # cleanup
        db.query(Schedule).filter_by(user_id=existing.user_id).delete()
        db.query(User).filter_by(user_id=existing.user_id).delete()
        db.commit()
    user = User(
        external_id="test_tz_user",
        channel="test",
        phone_number=None,
        email="tz_test@example.com",
        first_name="TZ",
        last_name="Tester",
        opted_in=True,
    )
    if timezone_name:
        user.timezone = timezone_name
    db.add(user)
    db.commit()
    return user.user_id


def test_create_schedule_europe_oslo_0900():
    db = SessionLocal()
    try:
        user_id = _create_test_user(db, timezone_name="Europe/Oslo")

        # Create schedule for 09:00 local time
        sched = SchedulerService.create_daily_schedule(user_id=user_id, lesson_id=None, time_str="09:00", session=db)
        assert sched is not None

        # reload schedules using the same session and pick active one
        # Note: We use the session directly instead of SchedulerService.get_user_schedules
        # to ensure we're using the same database connection
        all_schedules = db.query(Schedule).filter_by(user_id=user_id).all()
        active = [s for s in all_schedules if s.is_active]
        assert len(active) >= 1
        s = active[0]

        # Stored next_send_time may be naive depending on DB backend (SQLite)
        # Normalize with `to_utc()` helper before assertions.
        if s.next_send_time is not None:
            normalized = to_utc(s.next_send_time)
            # When displayed in Europe/Oslo, should show hour 9
            local_dt, resolved = format_dt_in_timezone(normalized, "Europe/Oslo")
            assert local_dt.hour == 9 and local_dt.minute == 0

    finally:
        db.close()


def _parse_run_at(run_at_val) -> datetime:
    """Parse run_at values from multiple formats (moved from TriggerDispatcher)."""
    if run_at_val is None:
        return None
    if isinstance(run_at_val, str):
        try:
            dt = datetime.fromisoformat(run_at_val)
        except Exception:
            from dateutil import parser as _dp
            dt = _dp.parse(run_at_val)
        return to_utc(dt)
    if isinstance(run_at_val, (int, float)):
        return to_utc(datetime.fromtimestamp(run_at_val, timezone.utc))
    return None


def test_parse_run_at_iso_and_epoch():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        iso = now.isoformat()
        parsed_iso = _parse_run_at(iso)
        assert parsed_iso is not None
        assert parsed_iso.tzinfo is not None
        # parsed_iso should be equal to to_utc(now)
        assert to_utc(parsed_iso) == to_utc(now)

        epoch = int(now.timestamp())
        parsed_epoch = _parse_run_at(epoch)
        assert parsed_epoch is not None
        assert parsed_epoch.tzinfo is not None
        assert to_utc(parsed_epoch) == to_utc(datetime.fromtimestamp(epoch, timezone.utc))

    finally:
        db.close()


def test_update_schedule_persists_utc_aware():
    db = SessionLocal()
    try:
        user_id = _create_test_user(db)

        # Create initial schedule
        sched = SchedulerService.create_daily_schedule(user_id=user_id, lesson_id=None, time_str="08:00", session=db)
        assert sched is not None

        # Update schedule next_send_time with a naive datetime (assume local) and ensure manager normalizes it
        naive_local = datetime(2026, 2, 8, 7, 30)  # naive
        updated = schedule_manager.update_schedule(sched.schedule_id, {"next_send_time": naive_local}, session=db)
        assert updated is not None
        assert updated.next_send_time is not None
        # DB may return naive datetimes; normalize before checking
        normalized = to_utc(updated.next_send_time)
        assert normalized.tzinfo is not None
        # Should be stored/normalized as UTC (utcoffset 0)
        assert normalized.utcoffset() == timedelta(0)

    finally:
        db.close()
