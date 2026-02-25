"""Unit tests for scheduler characterization scenarios.

Migrated from tests/test_scheduler_characterization.py to use new test fixtures.
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.memories import MemoryManager
from src.memories.constants import MemoryCategory, MemoryKey
from src.lessons.state import set_last_sent_lesson_id
from src.models.database import MessageLog, Schedule, User
from src.scheduler import SchedulerService
from src.scheduler.memory_helpers import get_pending_confirmation
from src.services.timezone_utils import format_dt_in_timezone
from src.triggers.trigger_dispatcher import TriggerDispatcher
from tests.fixtures.users import make_ready_user


class TestSchedulerCharacterization:
    """Characterization tests for scheduler behavior."""

    def test_normal_execution_sets_pending_confirmation(self, db_session, test_user_with_memories):
        """Given: A ready user with last lesson sent
        When: Executing scheduled task normally
        Then: Pending confirmation should be set
        """
        # Given: User with last sent lesson 1
        user_id = test_user_with_memories.user_id
        mm = MemoryManager(db_session)
        set_last_sent_lesson_id(mm, user_id, 1)
        
        # And: A daily schedule at 09:00
        schedule = SchedulerService.create_daily_schedule(
            user_id=user_id,
            lesson_id=None,
            time_str="09:00",
            session=db_session,
        )
        
        # Then: No pending confirmation initially
        assert get_pending_confirmation(mm, user_id) is None
        
        # When: Executing scheduled task
        SchedulerService.execute_scheduled_task(schedule.schedule_id, session=db_session)
        
        # Then: Pending confirmation should be set
        pending = get_pending_confirmation(mm, user_id)
        assert pending is not None
        assert pending.get("lesson_id") == 1
        assert pending.get("next_lesson_id") == 2
        
        # And: Message log should have outbound message
        outbound_count = (
            db_session.query(MessageLog)
            .filter_by(user_id=user_id, direction="outbound")
            .count()
        )
        assert outbound_count >= 1

    def test_recovery_execution_keeps_pending_confirmation_unset(self, db_session, monkeypatch):
        """Given: A ready user with overdue schedule
        When: Running recovery check
        Then: Should send recovery message, not set pending confirmation
        """
        # Given: User with last sent lesson 1
        user_id = make_ready_user(db_session, external_id="810002", first_name="Char")
        mm = MemoryManager(db_session)
        set_last_sent_lesson_id(mm, user_id, 1)
        
        # And: An overdue schedule (next_send_time in the past)
        schedule = SchedulerService.create_daily_schedule(
            user_id=user_id,
            lesson_id=None,
            time_str="09:00",
            session=db_session,
        )
        schedule.next_send_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        db_session.add(schedule)
        db_session.commit()
        
        # Then: No pending confirmation initially
        assert get_pending_confirmation(mm, user_id) is None
        
        # When: Running recovery check with mocked scheduler
        monkeypatch.setattr(
            SchedulerService,
            "get_scheduler",
            staticmethod(lambda: object()),
        )
        recovered = SchedulerService.run_recovery_check()
        assert recovered == 1
        
        # Then: Should not set pending confirmation (recovery message sent instead)
        db_session.expire_all()
        pending_after_recovery = get_pending_confirmation(mm, user_id)
        assert pending_after_recovery is None
        
        # And: Should have sent recovery message
        latest_log = (
            db_session.query(MessageLog)
            .filter_by(user_id=user_id, direction="outbound")
            .order_by(MessageLog.message_id.desc())
            .first()
        )
        assert latest_log is not None
        assert "Sorry I was not able to send this on time" in (latest_log.content or "")

    def test_simulate_daily_execution_sends_messages_but_keeps_schedule_timestamps(
        self, db_session, test_user_with_memories
    ):
        """Given: A ready user
        When: Executing scheduled task in simulate mode
        Then: Should send messages but not update schedule timestamps
        """
        # Given: User with last sent lesson 1
        user_id = test_user_with_memories.user_id
        mm = MemoryManager(db_session)
        set_last_sent_lesson_id(mm, user_id, 1)
        
        # And: A daily schedule
        schedule = SchedulerService.create_daily_schedule(
            user_id=user_id,
            lesson_id=None,
            time_str="09:00",
            session=db_session,
        )
        before_next_send = schedule.next_send_time
        before_last_sent = schedule.last_sent_at
        
        # When: Executing scheduled task in simulate mode
        messages = SchedulerService.execute_scheduled_task(
            schedule.schedule_id,
            simulate=True,
            session=db_session,
        )
        
        # Then: Messages should be returned but schedule should be unchanged
        db_session.refresh(schedule)
        assert isinstance(messages, list)
        assert messages
        assert schedule.next_send_time == before_next_send
        assert schedule.last_sent_at == before_last_sent
        
        # But: Pending confirmation should still be set
        pending = get_pending_confirmation(mm, user_id)
        assert pending is not None
        assert pending.get("lesson_id") == 1

    def test_one_time_execution_deactivates_and_removes_job(self, db_session, test_user_with_memories, monkeypatch):
        """Given: A one-time schedule
        When: Executing the scheduled task
        Then: Schedule should be deactivated and job removed
        """
        # Given: A one-time schedule in the future
        user_id = test_user_with_memories.user_id
        run_at = datetime.now(timezone.utc) + timedelta(minutes=2)
        schedule = SchedulerService.create_one_time_schedule(
            user_id=user_id,
            run_at=run_at,
            message="One-time characterization reminder",
            session=db_session,
        )
        
        removed_schedule_ids = []
        
        def _fake_remove_job_for_schedule(schedule_id: int):
            removed_schedule_ids.append(schedule_id)
        
        monkeypatch.setattr(
            "src.scheduler.jobs.remove_job_for_schedule",
            _fake_remove_job_for_schedule,
        )
        
        # When: Executing the scheduled task
        SchedulerService.execute_scheduled_task(schedule.schedule_id, session=db_session)
        
        # Then: Schedule should be deactivated
        db_session.refresh(schedule)
        assert schedule.is_active is False
        assert schedule.next_send_time is None
        assert schedule.last_sent_at is not None
        
        # And: Job should be marked for removal
        assert removed_schedule_ids == [schedule.schedule_id]

    def test_set_timezone_keeps_preferred_daily_time_local(self, db_session, monkeypatch):
        """Given: A user with preferred lesson time
        When: Changing timezone
        Then: Should keep local preferred time
        """
        # Given: A ready user with timezone set to Oslo
        user_id = make_ready_user(db_session, external_id="810005", first_name="Char")
        user = db_session.query(User).filter_by(user_id=user_id).first()
        user.timezone = "Europe/Oslo"
        db_session.add(user)
        db_session.commit()
        
        mm = MemoryManager(db_session)
        mm.store_memory(
            user_id=user_id,
            key=MemoryKey.PREFERRED_LESSON_TIME,
            value="10:15",
            category=MemoryCategory.PROFILE.value,
            source="test",
        )
        
        # And: A daily schedule at 09:00 UTC
        schedule = SchedulerService.create_daily_schedule(
            user_id=user_id,
            lesson_id=None,
            time_str="09:00",
            session=db_session,
        )
        
        # Mock send_message
        async def _fake_send_message(chat_id: int, text: str):
            return {"ok": True, "chat_id": chat_id, "text": text}
        
        from src import scheduler as scheduler_module
        monkeypatch.setattr(scheduler_module, "send_message", _fake_send_message)
        
        # When: Setting a new timezone via trigger
        dispatcher = TriggerDispatcher(db=db_session, memory_manager=mm)
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
        
        # Then: Timezone should be updated
        assert result.get("ok") is True
        db_session.refresh(user)
        db_session.refresh(schedule)
        assert user.timezone == "America/New_York"
        
        # And: Preferred local time (10:15) should be kept in new timezone
        local_dt, _ = format_dt_in_timezone(schedule.next_send_time, user.timezone)
        assert (local_dt.hour, local_dt.minute) == (10, 15)

