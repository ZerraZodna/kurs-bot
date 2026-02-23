"""Shared scheduler domain primitives.

This module centralizes schedule-type constants, classification helpers,
and APScheduler job-id formatting.
"""

from __future__ import annotations

from typing import Optional

# Canonical schedule type names/prefixes used throughout the scheduler domain.
SCHEDULE_TYPE_DAILY = "daily"
SCHEDULE_TYPE_ONE_TIME_PREFIX = "one_time"
SCHEDULE_TYPE_ONE_TIME_REMINDER = "one_time_reminder"

# APScheduler job-id format for schedule rows.
SCHEDULE_JOB_ID_PREFIX = "schedule_"


def is_daily_schedule_type(schedule_type: Optional[str]) -> bool:
    """Return True when schedule type is exactly daily."""
    return (schedule_type or "") == SCHEDULE_TYPE_DAILY


def is_daily_schedule_family(schedule_type: Optional[str]) -> bool:
    """Return True when schedule type starts with the daily prefix."""
    return (schedule_type or "").startswith(SCHEDULE_TYPE_DAILY)


def is_one_time_schedule_type(schedule_type: Optional[str]) -> bool:
    """Return True when schedule type starts with the one-time prefix."""
    return (schedule_type or "").startswith(SCHEDULE_TYPE_ONE_TIME_PREFIX)


def job_id_for_schedule(schedule_id: int) -> str:
    """Build APScheduler job id for a schedule id."""
    return f"{SCHEDULE_JOB_ID_PREFIX}{schedule_id}"
