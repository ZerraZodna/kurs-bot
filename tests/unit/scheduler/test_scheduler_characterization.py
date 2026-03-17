"""Unit tests for scheduler characterization scenarios.

Migrated from tests/test_scheduler_characterization.py to use new test fixtures.
"""

from datetime import datetime, timedelta, timezone

import pytest
from tests.fixtures.users import make_ready_user

from src.core.timezone import format_dt_in_timezone
from src.functions.executor import get_function_executor
from src.memories import MemoryManager
from src.memories.constants import MemoryCategory, MemoryKey
from src.models.database import Schedule, User
from src.scheduler import SchedulerService


class TestSchedulerCharacterization:
    """Characterization tests for scheduler behavior."""

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

    @pytest.mark.asyncio
    async def test_set_timezone_keeps_preferred_daily_time_local(self, db_session, monkeypatch):
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
        
        # When: Setting a new timezone via FunctionExecutor
        executor = get_function_executor()
        context = {
            "user_id": user_id,
            "session": db_session,
            "memory_manager": mm,
        }
        
        result = await executor.execute_single(
            "set_timezone",
            {"timezone": "America/New_York"},
            context
        )
        
        # Then: Timezone should be updated
        assert result.success is True
        assert result.result.get("ok") is True
        
        db_session.refresh(user)
        assert user.timezone == "America/New_York"
        
        # Refresh schedule from database to get updated next_send_time
        db_session.expire_all()
        schedule = db_session.query(Schedule).filter_by(schedule_id=schedule.schedule_id).first()
        
        # Debug: Print schedule state
        print(f"\n[DEBUG TEST] Schedule after update: id={schedule.schedule_id}")
        print(f"[DEBUG TEST]   next_send_time={schedule.next_send_time}")
        print(f"[DEBUG TEST]   cron={schedule.cron_expression}")
        print(f"[DEBUG TEST]   schedule_type={schedule.schedule_type}")
        print(f"[DEBUG TEST]   is_active={schedule.is_active}")
        print(f"[DEBUG TEST]   User timezone={user.timezone}")
        
        # And: Preferred local time (10:15) should be kept in new timezone
        local_dt, _ = format_dt_in_timezone(schedule.next_send_time, user.timezone)
        print(f"[DEBUG TEST]   Local time in {user.timezone}: {local_dt}")
        print(f"[DEBUG TEST]   Expected: (10, 15), Got: ({local_dt.hour}, {local_dt.minute})")
        
        assert (local_dt.hour, local_dt.minute) == (10, 15)
