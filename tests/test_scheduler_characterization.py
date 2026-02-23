from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.memories import MemoryManager
from src.memories.constants import MemoryCategory, MemoryKey
from src.lessons.state import set_last_sent_lesson_id
from src.models.database import MessageLog, Schedule, SessionLocal, User
from src.scheduler import SchedulerService
from src.scheduler.memory_helpers import get_pending_confirmation
from src.services.timezone_utils import format_dt_in_timezone
from src.triggers.trigger_dispatcher import TriggerDispatcher


def _make_ready_user(db, external_id: str) -> int:
    from tests.utils import make_ready_user

    return make_ready_user(db, external_id=external_id, first_name="Char")


def test_characterization_normal_execution_sets_pending_confirmation():
    db = SessionLocal()
    try:
        user_id = _make_ready_user(db, external_id="810001")
        mm = MemoryManager(db)
        set_last_sent_lesson_id(mm, user_id, 1)

        schedule = SchedulerService.create_daily_schedule(
            user_id=user_id,
            lesson_id=None,
            time_str="09:00",
            session=db,
        )
        assert get_pending_confirmation(mm, user_id) is None

        SchedulerService.execute_scheduled_task(schedule.schedule_id, session=db)

        pending = get_pending_confirmation(mm, user_id)
        assert pending is not None
        assert pending.get("lesson_id") == 1
        assert pending.get("next_lesson_id") == 2

        outbound_count = (
            db.query(MessageLog)
            .filter_by(user_id=user_id, direction="outbound")
            .count()
        )
        assert outbound_count >= 1
    finally:
        db.close()


def test_characterization_recovery_execution_keeps_pending_confirmation_unset(monkeypatch):
    db = SessionLocal()
    try:
        user_id = _make_ready_user(db, external_id="810002")
        mm = MemoryManager(db)
        set_last_sent_lesson_id(mm, user_id, 1)

        schedule = SchedulerService.create_daily_schedule(
            user_id=user_id,
            lesson_id=None,
            time_str="09:00",
            session=db,
        )
        schedule.next_send_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.add(schedule)
        db.commit()

        assert get_pending_confirmation(mm, user_id) is None

        monkeypatch.setattr(
            SchedulerService,
            "get_scheduler",
            staticmethod(lambda: object()),
        )
        recovered = SchedulerService.run_recovery_check()
        assert recovered == 1

        db.expire_all()
        pending_after_recovery = get_pending_confirmation(mm, user_id)
        assert pending_after_recovery is None

        latest_log = (
            db.query(MessageLog)
            .filter_by(user_id=user_id, direction="outbound")
            .order_by(MessageLog.message_id.desc())
            .first()
        )
        assert latest_log is not None
        assert "Sorry I was not able to send this on time" in (latest_log.content or "")
    finally:
        db.close()


def test_characterization_simulate_daily_execution_sends_messages_but_keeps_schedule_timestamps():
    db = SessionLocal()
    try:
        user_id = _make_ready_user(db, external_id="810003")
        mm = MemoryManager(db)
        set_last_sent_lesson_id(mm, user_id, 1)

        schedule = SchedulerService.create_daily_schedule(
            user_id=user_id,
            lesson_id=None,
            time_str="09:00",
            session=db,
        )
        before_next_send = schedule.next_send_time
        before_last_sent = schedule.last_sent_at

        messages = SchedulerService.execute_scheduled_task(
            schedule.schedule_id,
            simulate=True,
            session=db,
        )

        db.refresh(schedule)
        assert isinstance(messages, list)
        assert messages
        assert schedule.next_send_time == before_next_send
        assert schedule.last_sent_at == before_last_sent

        pending = get_pending_confirmation(mm, user_id)
        assert pending is not None
        assert pending.get("lesson_id") == 1

        outbound_count = (
            db.query(MessageLog)
            .filter_by(user_id=user_id, direction="outbound")
            .count()
        )
        assert outbound_count >= 1
    finally:
        db.close()


def test_characterization_one_time_execution_deactivates_and_removes_job(monkeypatch):
    db = SessionLocal()
    try:
        user_id = _make_ready_user(db, external_id="810004")
        run_at = datetime.now(timezone.utc) + timedelta(minutes=2)
        schedule = SchedulerService.create_one_time_schedule(
            user_id=user_id,
            run_at=run_at,
            message="One-time characterization reminder",
            session=db,
        )

        removed_schedule_ids = []

        def _fake_remove_job_for_schedule(schedule_id: int):
            removed_schedule_ids.append(schedule_id)

        monkeypatch.setattr(
            "src.scheduler.jobs.remove_job_for_schedule",
            _fake_remove_job_for_schedule,
        )

        SchedulerService.execute_scheduled_task(schedule.schedule_id, session=db)

        db.refresh(schedule)
        assert schedule.is_active is False
        assert schedule.next_send_time is None
        assert schedule.last_sent_at is not None
        assert removed_schedule_ids == [schedule.schedule_id]
    finally:
        db.close()


def test_characterization_set_timezone_keeps_preferred_daily_time_local(monkeypatch):
    db = SessionLocal()
    try:
        user_id = _make_ready_user(db, external_id="810005")
        user = db.query(User).filter_by(user_id=user_id).first()
        user.timezone = "Europe/Oslo"
        db.add(user)
        db.commit()

        mm = MemoryManager(db)
        mm.store_memory(
            user_id=user_id,
            key=MemoryKey.PREFERRED_LESSON_TIME,
            value="10:15",
            category=MemoryCategory.PROFILE.value,
            source="test",
        )

        schedule = SchedulerService.create_daily_schedule(
            user_id=user_id,
            lesson_id=None,
            time_str="09:00",
            session=db,
        )

        async def _fake_send_message(chat_id: int, text: str):
            return {"ok": True, "chat_id": chat_id, "text": text}

        from src import scheduler as scheduler_module

        monkeypatch.setattr(scheduler_module, "send_message", _fake_send_message)

        dispatcher = TriggerDispatcher(db=db, memory_manager=mm)
        result = dispatcher.dispatch(
            {
                "trigger_id": None,
                "name": "set_timezone",
                "action_type": "set_timezone",
                "score": 1.0,
                "threshold": 0.0,
            },
            {"user_id": user_id, "timezone": "America/New_York"},
        )
        assert result.get("ok") is True

        db.refresh(user)
        db.refresh(schedule)
        assert user.timezone == "America/New_York"

        local_dt, _ = format_dt_in_timezone(schedule.next_send_time, user.timezone)
        assert (local_dt.hour, local_dt.minute) == (10, 15)
    finally:
        db.close()
