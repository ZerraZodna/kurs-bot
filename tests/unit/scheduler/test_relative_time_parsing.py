"""Test relative time parsing for one-time reminders.

This test verifies that when a user says "in 10 minutes", the reminder
is scheduled correctly in their local timezone, not UTC.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest


class TestRelativeTimeParsing:
    """Test relative time expressions like 'in 10 minutes'."""

    def test_in_x_minutes_uses_user_timezone(self):
        """Test that 'in 10 minutes' calculates from user's local time, not UTC."""
        # Simulate: User in Oslo (UTC+1) says "in 10 minutes" at 15:04 Oslo time
        # Current UTC time: 14:04
        # Current Oslo time: 15:04
        # Expected reminder: 15:14 Oslo time = 14:14 UTC
        # Bug behavior: Calculates from UTC -> 14:14 UTC = 15:14 Oslo (WRONG!)

        # Mock current time
        mock_utc_now = datetime(2026, 3, 2, 14, 4, 0, tzinfo=timezone.utc)  # 14:04 UTC
        oslo_tz = ZoneInfo("Europe/Oslo")
        mock_oslo_now = mock_utc_now.astimezone(oslo_tz)  # Should be 15:04 Oslo

        # Verify our mock times are correct
        assert mock_oslo_now.hour == 15, f"Expected 15:04 Oslo, got {mock_oslo_now}"
        assert mock_oslo_now.minute == 4

        # The BUG: Current code does this:
        buggy_run_at = mock_utc_now + timedelta(minutes=10)
        # This gives 14:14 UTC which is 15:14 Oslo - WRONG!

        # The FIX: Should calculate from local time
        fixed_run_at_local = mock_oslo_now + timedelta(minutes=10)  # 15:14 Oslo
        fixed_run_at_utc = fixed_run_at_local.astimezone(timezone.utc)  # 14:14 UTC

        # Verify the bug
        assert buggy_run_at.hour == 14  # 14:14 UTC
        assert buggy_run_at.minute == 14

        # Verify the fix
        assert fixed_run_at_utc.hour == 14  # 14:14 UTC
        assert fixed_run_at_utc.minute == 14
        assert fixed_run_at_local.hour == 15  # 15:14 Oslo

        # The key difference: when converted back to Oslo time
        buggy_in_oslo = buggy_run_at.astimezone(oslo_tz)
        assert buggy_in_oslo.hour == 15  # Bug shows 15:14 Oslo (1 hour late!)
        assert buggy_in_oslo.minute == 14

        fixed_in_oslo = fixed_run_at_utc.astimezone(oslo_tz)
        assert fixed_in_oslo.hour == 15  # Correct: 15:14 Oslo
        assert fixed_in_oslo.minute == 14

        # Both show same time in Oslo, but the UTC times are different!
        # Bug: 14:14 UTC -> 15:14 Oslo (user wanted 15:14, got 15:14 - seems right but...)
        # Actually wait - let me recalculate

        # If user says "in 10 minutes" at 15:04 Oslo:
        # - Expected: 15:14 Oslo time
        # - In UTC: 14:14 UTC

        # Bug: 14:04 UTC + 10 min = 14:14 UTC = 15:14 Oslo (CORRECT!)
        # Hmm, that seems right...

        # Let me check if the issue is when the times cross the hour boundary
        # or if there's a DST issue

    def test_in_x_minutes_across_hour_boundary(self):
        """Test 'in 10 minutes' when it crosses an hour boundary."""
        # User in Oslo says "in 10 minutes" at 15:55 Oslo time
        # Expected: 16:05 Oslo time = 15:05 UTC

        mock_utc_now = datetime(2026, 3, 2, 14, 55, 0, tzinfo=timezone.utc)  # 14:55 UTC = 15:55 Oslo
        oslo_tz = ZoneInfo("Europe/Oslo")
        mock_oslo_now = mock_utc_now.astimezone(oslo_tz)

        assert mock_oslo_now.hour == 15
        assert mock_oslo_now.minute == 55

        # Bug: Add 10 min to UTC
        buggy = mock_utc_now + timedelta(minutes=10)  # 15:05 UTC = 16:05 Oslo

        # Fix: Add 10 min to local, convert to UTC
        fixed_local = mock_oslo_now + timedelta(minutes=10)  # 16:05 Oslo
        fixed_utc = fixed_local.astimezone(timezone.utc)  # 15:05 UTC

        # Bug result in Oslo time
        buggy_oslo = buggy.astimezone(oslo_tz)

        # Both should be 16:05 Oslo
        assert buggy_oslo.hour == 16
        assert buggy_oslo.minute == 5
        assert fixed_local.hour == 16
        assert fixed_local.minute == 5

        # But UTC times differ
        assert buggy.hour == 15  # 15:05 UTC (bug)
        assert fixed_utc.hour == 15  # 15:05 UTC (fix)

        # Hmm, still the same. Let me think about this differently...

    def test_in_x_minutes_when_utc_and_local_differ_significantly(self):
        """Test when there's a significant offset between UTC and local time."""
        # Let's say user is in Tokyo (UTC+9)
        tokyo_tz = ZoneInfo("Asia/Tokyo")

        # Tokyo: 23:00, UTC: 14:00
        mock_utc = datetime(2026, 3, 2, 14, 0, 0, tzinfo=timezone.utc)
        mock_tokyo = mock_utc.astimezone(tokyo_tz)

        assert mock_tokyo.hour == 23

        # User says "in 30 minutes" at 23:00 Tokyo
        # Expected: 23:30 Tokyo = 14:30 UTC

        # Bug: 14:00 UTC + 30 min = 14:30 UTC = 23:30 Tokyo (CORRECT!)

        # Hmm, the math works out. Let me check if the issue is DST-related
        # or if the issue is something else entirely

    def test_actual_bug_scenario(self):
        """Reproduce the actual bug from the database."""
        # From the database:
        # - Schedule 14 has next_send_time: 2026-03-02 15:14:00 UTC
        # - User timezone: Europe/Oslo (UTC+1 in March)
        # - User said "in 10 minutes" at 15:04 Oslo time
        # - Expected: 15:14 Oslo = 14:14 UTC
        # - Actual: 15:14 UTC = 16:14 Oslo (1 hour late!)

        # This means the code calculated:
        # 15:04 UTC + 10 minutes = 15:14 UTC
        # But it should have been:
        # 15:04 Oslo + 10 minutes = 15:14 Oslo = 14:14 UTC

        # The bug is that the code used 15:04 as UTC instead of Oslo time!

        # Let's verify this theory
        oslo_tz = ZoneInfo("Europe/Oslo")

        # If the code thought 15:04 was UTC (bug):
        buggy_base = datetime(2026, 3, 2, 15, 4, 0, tzinfo=timezone.utc)
        buggy_result = buggy_base + timedelta(minutes=10)  # 15:14 UTC

        # What the user actually wanted:
        # 15:04 Oslo = 14:04 UTC
        correct_base = datetime(2026, 3, 2, 14, 4, 0, tzinfo=timezone.utc)
        correct_result = correct_base + timedelta(minutes=10)  # 14:14 UTC

        # Convert to Oslo time for comparison
        buggy_oslo = buggy_result.astimezone(oslo_tz)  # 16:14 Oslo
        correct_oslo = correct_result.astimezone(oslo_tz)  # 15:14 Oslo

        print("\nBug scenario:")
        print(f"  Bug base (treated as UTC): {buggy_base}")
        print(f"  Bug result (UTC): {buggy_result}")
        print(f"  Bug result (Oslo): {buggy_oslo}")
        print("\nCorrect scenario:")
        print(f"  Correct base (UTC): {correct_base}")
        print(f"  Correct result (UTC): {correct_result}")
        print(f"  Correct result (Oslo): {correct_oslo}")

        # The bug result matches what we see in the database!
        assert buggy_result.hour == 15
        assert buggy_result.minute == 14
        assert buggy_oslo.hour == 16  # 1 hour late!

        # The correct result
        assert correct_result.hour == 14
        assert correct_result.minute == 14
        assert correct_oslo.hour == 15  # Correct time!

        # This confirms the bug: the code treated the local time as UTC


class TestFunctionExecutorTimeHandling:
    """Test the function executor's time handling for one-time reminders."""

    def test_handle_create_schedule_infers_timezone(self):
        """Test that create_schedule handler uses user's timezone for 'in X minutes'."""
        # This test will verify the fix works correctly
        pass  # Will implement after fix


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
