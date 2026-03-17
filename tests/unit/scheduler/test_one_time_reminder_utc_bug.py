"""Test to confirm the double UTC conversion bug in one-time reminders.

When creating a one-time reminder, the run_at time is converted to UTC in
operations.py, then converted again in jobs.py. This test verifies the bug
and will pass once the fix is applied.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo


class TestOneTimeReminderUTCConversion:
    """Test that one-time reminders are scheduled at the correct UTC time."""
    
    def test_run_at_not_double_converted(self):
        """
        Verify that run_at datetime is not double-converted to UTC.
        
        The bug: operations.py calls to_utc(run_at), then jobs.py calls
        to_utc(run_at) again. If run_at is already UTC-aware, the second
        call should not change it, but if there's any issue with the 
        timezone handling, it could shift the time incorrectly.
        """
        from src.core.timezone import to_utc
        
        # Simulate a user in Europe/Oslo (UTC+1 or UTC+2 depending on DST)
        local_tz = "Europe/Oslo"
        local_time = datetime(2026, 3, 2, 15, 14, 0)  # 15:14 local time
        
        # First conversion: local to UTC (as done in operations.py)
        local_aware = local_time.replace(tzinfo=ZoneInfo(local_tz))
        utc_time = local_aware.astimezone(timezone.utc)
        
        # This is what operations.py does - converts to UTC
        # utc_time should be 14:14 UTC (Oslo is UTC+1 in March)
        assert utc_time.hour == 14  # 15:14 Oslo = 14:14 UTC
        
        # Second conversion: what jobs.py does (the bug)
        # If to_utc is called again on an already-UTC datetime, 
        # it should return the same time
        utc_time_again = to_utc(utc_time)
        
        # These should be equal - if they're not, we have a double-conversion bug
        assert utc_time == utc_time_again, (
            f"Double UTC conversion changed the time! "
            f"Original UTC: {utc_time}, After second conversion: {utc_time_again}"
        )
    
    def test_sync_job_uses_correct_trigger_time(self):
        """
        Test that sync_job_for_schedule creates DateTrigger with correct time.
        
        This test verifies the actual behavior of sync_job_for_schedule
        by checking what DateTrigger is created.
        """
        from apscheduler.triggers.date import DateTrigger

        from src.scheduler.jobs import sync_job_for_schedule
        
        # Create a mock schedule with a specific UTC time
        run_at = datetime(2026, 3, 2, 14, 14, 0, tzinfo=timezone.utc)  # 14:14 UTC
        
        mock_schedule = Mock()
        mock_schedule.schedule_id = 123
        mock_schedule.schedule_type = "one_time_reminder"
        mock_schedule.next_send_time = run_at
        mock_schedule.cron_expression = f"once:{run_at.isoformat()}"
        
        # Track what trigger was created
        captured_trigger = None
        
        def capture_add_job(*args, **kwargs):
            nonlocal captured_trigger
            captured_trigger = kwargs.get("trigger")
            return Mock()
        
        # Mock the scheduler
        with patch("src.scheduler.core.SchedulerService") as mock_service_class:
            mock_scheduler = Mock()
            mock_scheduler.add_job = capture_add_job
            mock_service_class.get_scheduler.return_value = mock_scheduler
            
            # Call sync_job_for_schedule
            sync_job_for_schedule(mock_schedule)
            
            # Verify the trigger was created
            assert captured_trigger is not None, "No trigger was passed to add_job"
            assert isinstance(captured_trigger, DateTrigger), f"Expected DateTrigger, got {type(captured_trigger)}"
            
            # The trigger's run_date should be the exact UTC time we specified
            actual_run_date = captured_trigger.run_date
            assert actual_run_date == run_at, (
                f"Trigger run_date mismatch! "
                f"Expected: {run_at} (UTC), Got: {actual_run_date}"
            )
    
    def test_create_one_time_schedule_converts_to_utc_once(self):
        """
        Test that create_one_time_schedule converts to UTC exactly once.
        
        This verifies the full flow from local time input to UTC storage.
        The bug is that to_utc is called in BOTH operations.py AND manager.py,
        causing double conversion.
        """
        from src.scheduler.operations import create_one_time_schedule
        
        # Track what time is passed to create_schedule
        captured_times = []
        
        def capture_create_schedule(*args, **kwargs):
            captured_times.append(kwargs.get("next_send_time"))
            mock_schedule = Mock()
            mock_schedule.schedule_id = 456
            mock_schedule.schedule_type = "one_time_reminder"
            return mock_schedule
        
        # Mock the database and related functions
        with patch("src.scheduler.operations.schedule_manager.create_schedule", side_effect=capture_create_schedule), \
             patch("src.scheduler.operations.schedule_manager.find_existing_one_time_reminder", return_value=None), \
             patch("src.scheduler.operations.schedule_jobs") as mock_jobs, \
             patch("src.scheduler.operations.MemoryManager") as mock_mm_class:
            
            mock_mm = Mock()
            mock_mm_class.return_value = mock_mm
            
            # Create a one-time reminder for 15:14 local time (Oslo)
            local_tz = "Europe/Oslo"
            local_run_at = datetime(2026, 3, 2, 15, 14, 0, tzinfo=ZoneInfo(local_tz))
            
            # Expected UTC time: 14:14 UTC (Oslo is UTC+1 in March)
            expected_utc = local_run_at.astimezone(timezone.utc)
            assert expected_utc.hour == 14
            
            # Call the function with a mock session
            mock_session = Mock()
            result = create_one_time_schedule(
                user_id=1,
                run_at=local_run_at,
                message="Time to go out with the garbage",
                session=mock_session
            )
            
            # Verify the schedule was created
            assert len(captured_times) == 1, f"create_schedule was called {len(captured_times)} times"
            
            stored_next_send = captured_times[0]
            
            # The stored time should be in UTC
            assert stored_next_send is not None, "next_send_time was not set"
            assert stored_next_send.tzinfo is not None, "next_send_time is not timezone-aware"
            
            # Should be 14:14 UTC (15:14 Oslo = 14:14 UTC in March)
            # If it's 13:14, that means double conversion happened!
            assert stored_next_send.hour == 14, (
                f"Expected 14:14 UTC, got {stored_next_send.hour}:"
                f"{stored_next_send.minute:02d}. "
                f"This indicates double UTC conversion! "
                f"Input: {local_run_at} (Oslo), Expected UTC: {expected_utc}, "
                f"Actual: {stored_next_send}"
            )


class TestDateTriggerBehavior:
    """Test actual APScheduler DateTrigger behavior."""
    
    def test_date_trigger_fires_at_correct_utc_time(self):
        """
        Verify that DateTrigger fires at the correct UTC time.
        
        This test creates a DateTrigger and verifies it would fire
        at the expected moment.
        """
        from apscheduler.triggers.date import DateTrigger
        
        # Create a UTC time 2 seconds in the future
        future_utc = datetime.now(timezone.utc) + timedelta(seconds=2)
        
        # Create trigger
        trigger = DateTrigger(run_date=future_utc, timezone=timezone.utc)
        
        # Verify the trigger's next fire time is what we expect
        next_fire = trigger.get_next_fire_time(None, future_utc - timedelta(seconds=1))
        assert next_fire is not None, "Trigger should have a next fire time"
        
        # The next fire time should match our specified time
        assert next_fire == future_utc, (
            f"Trigger next fire time mismatch! "
            f"Expected: {future_utc}, Got: {next_fire}"
        )
    
    def test_date_trigger_with_pre_converted_utc(self):
        """
        Test DateTrigger when given a datetime that's already been converted to UTC.
        
        This simulates the actual flow where operations.py converts to UTC,
        then manager.py converts again (which should be idempotent).
        """
        from apscheduler.triggers.date import DateTrigger

        from src.core.timezone import to_utc
        
        # Start with local time (Oslo 15:14)
        local_time = datetime(2026, 3, 2, 15, 14, 0, tzinfo=ZoneInfo("Europe/Oslo"))
        
        # First conversion (as in operations.py)
        utc_1 = to_utc(local_time)
        assert utc_1.hour == 14  # Should be 14:14 UTC
        
        # Second conversion (as in manager.py or jobs.py)
        utc_2 = to_utc(utc_1)
        assert utc_2 == utc_1  # Should be identical
        
        # Create trigger with the double-converted time
        trigger = DateTrigger(run_date=utc_2, timezone=timezone.utc)
        
        # The trigger should still fire at the correct moment
        # 14:14 UTC = 15:14 Oslo
        expected_fire_time = local_time.astimezone(timezone.utc)
        actual_fire_time = trigger.get_next_fire_time(None, datetime(2026, 3, 2, 14, 0, 0, tzinfo=timezone.utc))
        
        assert actual_fire_time == expected_fire_time, (
            f"Trigger fire time incorrect after double UTC conversion! "
            f"Expected: {expected_fire_time}, Got: {actual_fire_time}"
        )


class TestSchedulerJobTimezoneHandling:
    """Additional tests for scheduler job timezone handling."""
    
    def test_date_trigger_timezone_consistency(self):
        """
        Verify that DateTrigger is created with consistent timezone handling.
        
        APScheduler's DateTrigger should fire at the correct time regardless
        of the timezone it's created with, as long as the run_date is correct.
        """
        from apscheduler.triggers.date import DateTrigger
        
        # Create a UTC datetime
        utc_time = datetime(2026, 3, 2, 14, 14, 0, tzinfo=timezone.utc)
        
        # Create trigger with UTC timezone
        trigger_utc = DateTrigger(run_date=utc_time, timezone=timezone.utc)
        
        # The trigger's run_date should be the same
        assert trigger_utc.run_date == utc_time
        
        # Create the same time in a different timezone
        oslo_time = utc_time.astimezone(ZoneInfo("Europe/Oslo"))
        trigger_oslo = DateTrigger(run_date=oslo_time, timezone=ZoneInfo("Europe/Oslo"))
        
        # Both triggers should represent the same moment in time
        assert trigger_utc.run_date.astimezone(timezone.utc) == \
               trigger_oslo.run_date.astimezone(timezone.utc)
    
    def test_to_utc_idempotent(self):
        """
        Test that to_utc is idempotent - calling it twice should give the same result.
        
        This is the core of the bug: if to_utc is called on an already-UTC datetime,
        it should return the same datetime unchanged.
        """
        from src.core.timezone import to_utc
        
        # Start with a naive datetime (no timezone)
        naive_dt = datetime(2026, 3, 2, 15, 14, 0)
        
        # First conversion - assume UTC
        utc_1 = to_utc(naive_dt)
        
        # Second conversion - should be the same
        utc_2 = to_utc(utc_1)
        
        assert utc_1 == utc_2, (
            f"to_utc is not idempotent! "
            f"First call: {utc_1}, Second call: {utc_2}"
        )
        
        # Also test with an aware non-UTC datetime
        oslo_dt = datetime(2026, 3, 2, 15, 14, 0, tzinfo=ZoneInfo("Europe/Oslo"))
        utc_from_oslo_1 = to_utc(oslo_dt)
        utc_from_oslo_2 = to_utc(utc_from_oslo_1)
        
        assert utc_from_oslo_1 == utc_from_oslo_2, (
            f"to_utc is not idempotent on converted datetime! "
            f"First: {utc_from_oslo_1}, Second: {utc_from_oslo_2}"
        )
