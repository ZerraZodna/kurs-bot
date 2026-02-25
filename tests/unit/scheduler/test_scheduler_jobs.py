"""Unit tests for scheduler jobs.

Migrated from tests/test_scheduler_jobs.py to use new test fixtures.
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.scheduler import jobs


class FakeSchedule:
    """Fake schedule object for testing job sync."""
    def __init__(self, schedule_id, schedule_type, cron_expression=None, next_send_time=None):
        self.schedule_id = schedule_id
        self.schedule_type = schedule_type
        self.cron_expression = cron_expression
        self.next_send_time = next_send_time


class TestSchedulerJobs:
    """Tests for scheduler job management."""

    def test_init_scheduler(self):
        """Should initialize the scheduler."""
        # Given: The scheduler module
        # When: Initializing the scheduler
        sched = jobs.init_scheduler()
        
        # Then: Scheduler should be created
        assert sched is not None
        
        # Cleanup
        jobs.shutdown_scheduler()

    def test_sync_and_remove_one_time_job(self):
        """Should sync and remove one-time reminder jobs."""
        # Given: An initialized scheduler
        sched = jobs.init_scheduler()
        assert sched is not None
        
        # When: Creating a one-time schedule and syncing
        run_at = datetime.now(timezone.utc) + timedelta(seconds=5)
        fake_schedule = FakeSchedule(9999, "one_time_reminder", next_send_time=run_at)
        jobs.sync_job_for_schedule(fake_schedule)
        
        # Then: Job should exist in scheduler
        job = sched.get_job(f"schedule_{fake_schedule.schedule_id}")
        assert job is not None
        
        # When: Removing the job
        jobs.remove_job_for_schedule(fake_schedule.schedule_id)
        
        # Then: Job should no longer exist
        assert sched.get_job(f"schedule_{fake_schedule.schedule_id}") is None
        
        # Cleanup
        jobs.shutdown_scheduler()

    def test_sync_and_remove_cron_job(self):
        """Should sync and remove cron-based daily jobs."""
        # Given: An initialized scheduler
        sched = jobs.init_scheduler()
        assert sched is not None
        
        # When: Creating a daily (cron) schedule and syncing
        fake_schedule = FakeSchedule(10000, "daily", cron_expression="0 0 * * *")
        jobs.sync_job_for_schedule(fake_schedule)
        
        # Then: Job should exist in scheduler
        job2 = sched.get_job(f"schedule_{fake_schedule.schedule_id}")
        assert job2 is not None
        
        # When: Removing the job
        jobs.remove_job_for_schedule(fake_schedule.schedule_id)
        
        # Then: Job should no longer exist
        assert sched.get_job(f"schedule_{fake_schedule.schedule_id}") is None
        
        # Cleanup
        jobs.shutdown_scheduler()

    def test_sync_job_without_time_returns_early(self):
        """Should handle one-time schedule without next_send_time."""
        # Given: An initialized scheduler
        sched = jobs.init_scheduler()
        
        # When: Creating a one-time schedule without next_send_time
        fake_schedule = FakeSchedule(9998, "one_time_reminder", next_send_time=None)
        jobs.sync_job_for_schedule(fake_schedule)
        
        # Then: Job should not be added
        job = sched.get_job(f"schedule_{fake_schedule.schedule_id}")
        assert job is None
        
        # Cleanup
        jobs.shutdown_scheduler()

    def test_sync_job_without_cron_returns_early(self):
        """Should handle non-cron schedule without cron_expression."""
        # Given: An initialized scheduler
        sched = jobs.init_scheduler()
        
        # When: Creating a schedule without cron_expression
        fake_schedule = FakeSchedule(9997, "daily", cron_expression=None)
        jobs.sync_job_for_schedule(fake_schedule)
        
        # Then: Job should not be added
        job = sched.get_job(f"schedule_{fake_schedule.schedule_id}")
        assert job is None
        
        # Cleanup
        jobs.shutdown_scheduler()

    def test_job_id_for_schedule(self):
        """Should return correct job ID format."""
        # When: Getting job ID for a schedule
        job_id = jobs.job_id_for_schedule(12345)
        
        # Then: Should follow expected format
        assert job_id == "schedule_12345"

