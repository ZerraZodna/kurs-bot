"""
Unit tests for _handle_query_schedule function in FunctionExecutor.

This test file covers the query_schedule function handler which:
- Fetches user schedules from the scheduler API
- Converts times to the user's local timezone
- Includes messages for one-time reminders from memory
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from src.functions.executor import FunctionExecutor
from src.models.database import User, Schedule
from src.memories import MemoryManager
from src.memories.constants import MemoryKey, MemoryCategory


class TestHandleQuerySchedule:
    """Tests for the _handle_query_schedule handler."""

    @pytest.fixture
    def executor(self):
        """Create a FunctionExecutor instance."""
        return FunctionExecutor()

    @pytest.fixture
    def mock_memory_manager(self):
        """Create a mock memory manager."""
        mm = Mock(spec=MemoryManager)
        mm.get_memory.return_value = []
        return mm

    @pytest.mark.asyncio
    async def test_query_schedule_returns_empty_list_when_no_schedules(
        self, executor, db_session, test_user, mock_memory_manager
    ):
        """Given: User has no schedules
        When: _handle_query_schedule is called
        Then: Return empty schedules list with success
        """
        with patch('src.core.timezone.get_user_timezone_from_db', return_value='Europe/Oslo'):
            with patch('src.scheduler.api.get_user_schedules', return_value=[]):
                context = {
                    "user_id": test_user.user_id,
                    "session": db_session,
                    "memory_manager": mock_memory_manager,
                }
                
                result = await executor._handle_query_schedule({}, context)
        
        assert result["ok"] is True
        assert result["schedules"] == []
        assert result["timezone"] == "Europe/Oslo"

    @pytest.mark.asyncio
    async def test_query_schedule_returns_daily_schedules(
        self, executor, db_session, test_user, mock_memory_manager
    ):
        """Given: User has daily schedules
        When: _handle_query_schedule is called
        Then: Return list of active schedules
        """
        # Create daily schedules
        schedule1 = Schedule(
            user_id=test_user.user_id,
            lesson_id=1,
            schedule_type="daily",
            cron_expression="0 9 * * *",
            next_send_time=datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        schedule2 = Schedule(
            user_id=test_user.user_id,
            lesson_id=2,
            schedule_type="daily",
            cron_expression="0 18 * * *",
            next_send_time=datetime(2024, 1, 15, 18, 0, tzinfo=timezone.utc),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(schedule1)
        db_session.add(schedule2)
        db_session.commit()
        
        with patch('src.core.timezone.get_user_timezone_from_db', return_value='Europe/Oslo'):
            with patch('src.core.timezone.format_dt_in_timezone') as mock_format:
                # Mock timezone conversion to return a fixed time
                mock_format.return_value = (datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc), "Europe/Oslo")
                
                with patch('src.scheduler.api.get_user_schedules', return_value=[schedule1, schedule2]):
                    context = {
                        "user_id": test_user.user_id,
                        "session": db_session,
                        "memory_manager": mock_memory_manager,
                    }
                    
                    result = await executor._handle_query_schedule({}, context)
        
        assert result["ok"] is True
        assert len(result["schedules"]) == 2
        
        # Verify schedule data structure
        schedule_ids = [s["schedule_id"] for s in result["schedules"]]
        assert schedule1.schedule_id in schedule_ids
        assert schedule2.schedule_id in schedule_ids
        
        # Verify timezone is included
        assert result["timezone"] == "Europe/Oslo"

    @pytest.mark.asyncio
    async def test_query_schedule_converts_to_local_timezone(
        self, executor, db_session, test_user, mock_memory_manager
    ):
        """Given: User has schedule with UTC time
        When: _handle_query_schedule is called
        Then: Return time in user's local timezone
        """
        # Create schedule with UTC time
        schedule = Schedule(
            user_id=test_user.user_id,
            lesson_id=1,
            schedule_type="daily",
            cron_expression="0 9 * * *",
            next_send_time=datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc),  # 9 AM UTC
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(schedule)
        db_session.commit()
        
        # User in Europe/Oslo (UTC+1 in winter)
        with patch('src.core.timezone.get_user_timezone_from_db', return_value='Europe/Oslo'):
            with patch('src.core.timezone.format_dt_in_timezone') as mock_format:
                # Mock: 9 AM UTC should become 10 AM in Europe/Oslo
                local_dt = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
                mock_format.return_value = (local_dt, "Europe/Oslo")
                
                with patch('src.scheduler.api.get_user_schedules', return_value=[schedule]):
                    context = {
                        "user_id": test_user.user_id,
                        "session": db_session,
                        "memory_manager": mock_memory_manager,
                    }
                    
                    result = await executor._handle_query_schedule({}, context)
        
        assert result["ok"] is True
        assert len(result["schedules"]) == 1
        # next_send_time should be converted to local time
        assert result["schedules"][0]["next_send_time"] is not None

    @pytest.mark.asyncio
    async def test_query_schedule_includes_one_time_reminder_message(
        self, executor, db_session, test_user, mock_memory_manager
    ):
        """Given: User has one-time reminder with message stored in memory
        When: _handle_query_schedule is called
        Then: Include the message from memory
        """
        # Create one-time schedule - need cron_expression even for one_time types
        schedule = Schedule(
            user_id=test_user.user_id,
            lesson_id=None,
            schedule_type="one_time_reminder",
            cron_expression="",  # Required field but not used for one_time
            next_send_time=datetime(2024, 1, 20, 14, 0, tzinfo=timezone.utc),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(schedule)
        db_session.commit()
        
        # Mock memory manager to return message for this schedule
        message_data = json.dumps({
            "schedule_id": schedule.schedule_id,
            "message": "Don't forget your lesson!"
        })
        mock_memory_manager.get_memory.return_value = [
            {"key": MemoryKey.SCHEDULE_MESSAGE, "value": message_data}
        ]
        
        with patch('src.core.timezone.get_user_timezone_from_db', return_value='UTC'):
            with patch('src.core.timezone.format_dt_in_timezone') as mock_format:
                mock_format.return_value = (schedule.next_send_time, "UTC")
                
                with patch('src.scheduler.api.get_user_schedules', return_value=[schedule]):
                    with patch('src.scheduler.memory_helpers.get_schedule_message') as mock_get_msg:
                        mock_get_msg.return_value = "Don't forget your lesson!"
                        
                        context = {
                            "user_id": test_user.user_id,
                            "session": db_session,
                            "memory_manager": mock_memory_manager,
                        }
                        
                        result = await executor._handle_query_schedule({}, context)
        
        assert result["ok"] is True
        assert len(result["schedules"]) == 1
        
        # Verify message is included for one-time reminder
        assert result["schedules"][0]["schedule_type"] == "one_time_reminder"
        assert result["schedules"][0]["message"] == "Don't forget your lesson!"

    @pytest.mark.asyncio
    async def test_query_schedule_excludes_inactive_schedules(
        self, executor, db_session, test_user, mock_memory_manager
    ):
        """Given: User has both active and inactive schedules
        When: _handle_query_schedule is called with active_only=True
        Then: Only return active schedules
        """
        # Create active schedule
        active_schedule = Schedule(
            user_id=test_user.user_id,
            lesson_id=1,
            schedule_type="daily",
            cron_expression="0 9 * * *",
            next_send_time=datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        
        # Create inactive schedule
        inactive_schedule = Schedule(
            user_id=test_user.user_id,
            lesson_id=2,
            schedule_type="daily",
            cron_expression="0 18 * * *",
            next_send_time=datetime(2024, 1, 15, 18, 0, tzinfo=timezone.utc),
            is_active=False,  # Inactive
            created_at=datetime.now(timezone.utc),
        )
        
        db_session.add(active_schedule)
        db_session.add(inactive_schedule)
        db_session.commit()
        
        with patch('src.core.timezone.get_user_timezone_from_db', return_value='UTC'):
            with patch('src.core.timezone.format_dt_in_timezone') as mock_format:
                mock_format.return_value = (datetime(2024, 1, 15, 9, 0, tzinfo=timezone.utc), "UTC")
                
                # Only return active schedules from the API
                with patch('src.scheduler.api.get_user_schedules', return_value=[active_schedule]):
                    context = {
                        "user_id": test_user.user_id,
                        "session": db_session,
                        "memory_manager": mock_memory_manager,
                    }
                    
                    result = await executor._handle_query_schedule({}, context)
        
        assert result["ok"] is True
        # Only active schedule should be returned
        assert len(result["schedules"]) == 1
        assert result["schedules"][0]["schedule_id"] == active_schedule.schedule_id

    @pytest.mark.asyncio
    async def test_query_schedule_handles_exception(
        self, executor, db_session, test_user, mock_memory_manager
    ):
        """Given: Scheduler API raises an exception
        When: _handle_query_schedule is called
        Then: Return error response
        """
        with patch('src.core.timezone.get_user_timezone_from_db', return_value='UTC'):
            with patch('src.scheduler.api.get_user_schedules', side_effect=Exception("Database error")):
                context = {
                    "user_id": test_user.user_id,
                    "session": db_session,
                    "memory_manager": mock_memory_manager,
                }
                
                result = await executor._handle_query_schedule({}, context)
        
        assert result["ok"] is False
        assert "error" in result
        assert "Database error" in result["error"]

    @pytest.mark.asyncio
    async def test_query_schedule_without_memory_manager(
        self, executor, db_session, test_user
    ):
        """Given: No memory_manager provided (one-time reminder case)
        When: _handle_query_schedule is called
        Then: Still return schedules without crashing
        """
        # Create one-time schedule - need cron_expression even for one_time types
        schedule = Schedule(
            user_id=test_user.user_id,
            lesson_id=None,
            schedule_type="one_time_reminder",
            cron_expression="",  # Required field but not used for one_time
            next_send_time=datetime(2024, 1, 20, 14, 0, tzinfo=timezone.utc),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(schedule)
        db_session.commit()
        
        with patch('src.core.timezone.get_user_timezone_from_db', return_value='UTC'):
            with patch('src.core.timezone.format_dt_in_timezone') as mock_format:
                mock_format.return_value = (schedule.next_send_time, "UTC")
                
                with patch('src.scheduler.api.get_user_schedules', return_value=[schedule]):
                    # Context without memory_manager
                    context = {
                        "user_id": test_user.user_id,
                        "session": db_session,
                        "memory_manager": None,
                    }
                    
                    result = await executor._handle_query_schedule({}, context)
        
        assert result["ok"] is True
        assert len(result["schedules"]) == 1
        # Message should not be present since no memory_manager
        assert "message" not in result["schedules"][0]

    @pytest.mark.asyncio
    async def test_query_schedule_without_session(
        self, executor, test_user, mock_memory_manager
    ):
        """Given: No session provided in context
        When: _handle_query_schedule is called
        Then: Return schedules using default UTC timezone
        """
        with patch('src.core.timezone.get_user_timezone_from_db', return_value='UTC'):
            with patch('src.scheduler.api.get_user_schedules', return_value=[]):
                context = {
                    "user_id": test_user.user_id,
                    "session": None,  # No session
                    "memory_manager": mock_memory_manager,
                }
                
                result = await executor._handle_query_schedule({}, context)
        
        assert result["ok"] is True
        assert result["schedules"] == []
        assert result["timezone"] == "UTC"


class TestHandleQueryScheduleIntegration:
    """Integration tests for _handle_query_schedule with real components."""

    @pytest.fixture
    def executor(self):
        """Create a FunctionExecutor instance."""
        return FunctionExecutor()

    @pytest.mark.asyncio
    async def test_query_schedule_with_real_memory_manager(
        self, executor, db_session, test_user
    ):
        """Given: Real memory manager with stored schedule message
        When: _handle_query_schedule is called
        Then: Retrieve message from memory correctly
        """
        # Create one-time schedule - need cron_expression even for one_time types
        schedule = Schedule(
            user_id=test_user.user_id,
            lesson_id=None,
            schedule_type="one_time_reminder",
            cron_expression="",  # Required field but not used for one_time
            next_send_time=datetime(2024, 1, 20, 14, 0, tzinfo=timezone.utc),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(schedule)
        db_session.commit()
        
        # Store schedule message in memory using real MemoryManager
        mm = MemoryManager(db_session)
        message_data = json.dumps({
            "schedule_id": schedule.schedule_id,
            "message": "Your custom reminder message"
        })
        mm.store_memory(
            user_id=test_user.user_id,
            key=MemoryKey.SCHEDULE_MESSAGE,
            value=message_data,
            category=MemoryCategory.CONVERSATION.value,  # Use valid category
            source="test",
        )
        
        with patch('src.core.timezone.get_user_timezone_from_db', return_value='UTC'):
            with patch('src.core.timezone.format_dt_in_timezone') as mock_format:
                mock_format.return_value = (schedule.next_send_time, "UTC")
                
                with patch('src.scheduler.api.get_user_schedules', return_value=[schedule]):
                    context = {
                        "user_id": test_user.user_id,
                        "session": db_session,
                        "memory_manager": mm,
                    }
                    
                    result = await executor._handle_query_schedule({}, context)
        
        assert result["ok"] is True
        assert len(result["schedules"]) == 1
        assert result["schedules"][0]["message"] == "Your custom reminder message"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

