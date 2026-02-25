"""Unit tests for scheduler domain predicates and helpers.

Refactored to use new test fixtures from tests/fixtures/
"""

import pytest
from sqlalchemy.orm import Session

from src.scheduler import jobs
from src.scheduler.domain import (
    SCHEDULE_TYPE_DAILY,
    SCHEDULE_TYPE_ONE_TIME_REMINDER,
    is_daily_schedule_type,
    is_daily_schedule_family,
    is_one_time_schedule_type,
    job_id_for_schedule,
)


class TestScheduleTypePredicates:
    """Test suite for schedule type predicate functions."""

    def test_is_daily_schedule_type(self):
        """Should correctly identify daily schedule types."""
        # Then: Should return True for daily type
        assert is_daily_schedule_type(SCHEDULE_TYPE_DAILY) is True
        
        # And: Should return False for non-daily types
        assert is_daily_schedule_type("daily_custom") is False
        assert is_daily_schedule_type(None) is False

    def test_is_daily_schedule_family(self):
        """Should identify all schedules in daily family."""
        # Then: Daily type is in family
        assert is_daily_schedule_family(SCHEDULE_TYPE_DAILY) is True
        
        # And: Custom daily types are also in the family
        assert is_daily_schedule_family("daily_custom") is True
        
        # And: Non-daily types are not in the family
        assert is_daily_schedule_family("weekly") is False
        assert is_daily_schedule_family(None) is False

    def test_is_one_time_schedule_type(self):
        """Should correctly identify one-time schedule types."""
        # Then: Should return True for one-time types
        assert is_one_time_schedule_type(SCHEDULE_TYPE_ONE_TIME_REMINDER) is True
        
        # And: Custom one-time types are also recognized
        assert is_one_time_schedule_type("one_time_custom") is True
        
        # And: Non one-time types return False
        assert is_one_time_schedule_type("daily") is False
        assert is_one_time_schedule_type(None) is False


class TestJobIdHelper:
    """Test suite for job ID helper function."""

    def test_job_id_for_schedule(self, db_session: Session, test_user):
        """Should generate correct job ID for schedule."""
        # Then: Should match the jobs module's implementation
        assert job_id_for_schedule(42) == "schedule_42"
        assert jobs.job_id_for_schedule(42) == "schedule_42"

