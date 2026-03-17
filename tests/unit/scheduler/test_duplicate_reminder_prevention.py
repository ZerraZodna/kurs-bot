"""
Tests for duplicate reminder prevention in the scheduler.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.scheduler.manager import find_existing_one_time_reminder
from src.scheduler.operations import create_one_time_schedule
from src.scheduler.domain import SCHEDULE_TYPE_ONE_TIME_REMINDER


class TestDuplicateReminderPrevention:
    """Test that duplicate one-time reminders are prevented."""
    
    def test_find_existing_one_time_reminder_exact_match(self):
        """Test finding an existing reminder at the exact same time."""
        # Create a mock schedule
        mock_schedule = MagicMock()
        mock_schedule.schedule_id = 1
        mock_schedule.schedule_type = SCHEDULE_TYPE_ONE_TIME_REMINDER
        mock_schedule.next_send_time = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        mock_schedule.is_active = True
        
        # Mock the session query
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.all.return_value = [mock_schedule]
        
        # Search for the same time
        run_at = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        result = find_existing_one_time_reminder(
            user_id=123,
            run_at=run_at,
            session=mock_session,
            tolerance_seconds=60,
        )
        
        assert result is not None
        assert result.schedule_id == 1
    
    def test_find_existing_one_time_reminder_within_tolerance(self):
        """Test finding an existing reminder within the tolerance window."""
        # Create a mock schedule
        mock_schedule = MagicMock()
        mock_schedule.schedule_id = 1
        mock_schedule.schedule_type = SCHEDULE_TYPE_ONE_TIME_REMINDER
        mock_schedule.next_send_time = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        mock_schedule.is_active = True
        
        # Mock the session query
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.all.return_value = [mock_schedule]
        
        # Search for a time 30 seconds later (within 60s tolerance)
        run_at = datetime(2024, 1, 15, 14, 30, 30, tzinfo=timezone.utc)
        result = find_existing_one_time_reminder(
            user_id=123,
            run_at=run_at,
            session=mock_session,
            tolerance_seconds=60,
        )
        
        assert result is not None
        assert result.schedule_id == 1
    
    def test_find_existing_one_time_reminder_outside_tolerance(self):
        """Test that reminders outside the tolerance window are not matched."""
        # Create a mock schedule
        mock_schedule = MagicMock()
        mock_schedule.schedule_id = 1
        mock_schedule.schedule_type = SCHEDULE_TYPE_ONE_TIME_REMINDER
        mock_schedule.next_send_time = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        mock_schedule.is_active = True
        
        # Mock the session query
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.all.return_value = [mock_schedule]
        
        # Search for a time 2 minutes later (outside 60s tolerance)
        run_at = datetime(2024, 1, 15, 14, 32, 0, tzinfo=timezone.utc)
        result = find_existing_one_time_reminder(
            user_id=123,
            run_at=run_at,
            session=mock_session,
            tolerance_seconds=60,
        )
        
        assert result is None
    
    def test_find_existing_one_time_reminder_different_type(self):
        """Test that daily schedules are not matched as one-time reminders."""
        # Create a mock daily schedule
        mock_schedule = MagicMock()
        mock_schedule.schedule_id = 1
        mock_schedule.schedule_type = "daily"  # Not a one-time reminder
        mock_schedule.next_send_time = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        mock_schedule.is_active = True
        
        # Mock the session query
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.all.return_value = [mock_schedule]
        
        # Search for the same time
        run_at = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        result = find_existing_one_time_reminder(
            user_id=123,
            run_at=run_at,
            session=mock_session,
            tolerance_seconds=60,
        )
        
        # Should not match because it's a daily schedule, not one-time
        assert result is None
    
    def test_find_existing_one_time_reminder_inactive(self):
        """Test that inactive schedules are not matched."""
        # Create a mock inactive schedule
        mock_schedule = MagicMock()
        mock_schedule.schedule_id = 1
        mock_schedule.schedule_type = SCHEDULE_TYPE_ONE_TIME_REMINDER
        mock_schedule.next_send_time = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        mock_schedule.is_active = False  # Inactive
        
        # Mock the session query - should not return inactive schedules
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.all.return_value = []
        
        # Search for the same time
        run_at = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        result = find_existing_one_time_reminder(
            user_id=123,
            run_at=run_at,
            session=mock_session,
            tolerance_seconds=60,
        )
        
        assert result is None


class TestCreateOneTimeScheduleDeduplication:
    """Test that create_one_time_schedule prevents duplicates."""
    
    @pytest.mark.asyncio
    async def test_create_one_time_schedule_returns_existing_on_duplicate(self):
        """Test that creating a duplicate returns the existing schedule."""
        # Mock existing schedule
        existing_schedule = MagicMock()
        existing_schedule.schedule_id = 42
        
        # Mock the find_existing_one_time_reminder to return the existing schedule
        with patch('src.scheduler.operations.schedule_manager.find_existing_one_time_reminder') as mock_find:
            mock_find.return_value = existing_schedule
            
            # Mock MemoryManager
            with patch('src.scheduler.operations.MemoryManager') as mock_mm_class:
                mock_mm = MagicMock()
                mock_mm_class.return_value = mock_mm
                
                # Mock sync_job_for_schedule
                with patch('src.scheduler.operations.schedule_jobs.sync_job_for_schedule'):
                    
                    run_at = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
                    result = create_one_time_schedule(
                        user_id=123,
                        run_at=run_at,
                        message="Test reminder",
                        session=None,  # Will create its own session
                    )
                    
                    # Should return the existing schedule, not create a new one
                    assert result.schedule_id == 42
                    # Verify find was called
                    mock_find.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_one_time_schedule_creates_new_when_no_duplicate(self):
        """Test that a new schedule is created when no duplicate exists."""
        # Mock find_existing_one_time_reminder to return None (no duplicate)
        with patch('src.scheduler.operations.schedule_manager.find_existing_one_time_reminder') as mock_find:
            mock_find.return_value = None
            
            # Mock create_schedule to return a new schedule
            mock_new_schedule = MagicMock()
            mock_new_schedule.schedule_id = 99
            
            with patch('src.scheduler.operations.schedule_manager.create_schedule') as mock_create:
                mock_create.return_value = mock_new_schedule
                
                # Mock MemoryManager
                with patch('src.scheduler.operations.MemoryManager') as mock_mm_class:
                    mock_mm = MagicMock()
                    mock_mm_class.return_value = mock_mm
                    
                    # Mock sync_job_for_schedule
                    with patch('src.scheduler.operations.schedule_jobs.sync_job_for_schedule'):
                        
                        run_at = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
                        result = create_one_time_schedule(
                            user_id=123,
                            run_at=run_at,
                            message="Test reminder",
                            session=None,
                        )
                        
                        # Should create a new schedule
                        assert result.schedule_id == 99
                        # Verify create was called
                        mock_create.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
