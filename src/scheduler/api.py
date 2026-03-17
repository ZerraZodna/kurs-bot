"""
Scheduler Public API Facade.

This module provides a clean, public API for all schedule operations.
All other modules should use this API instead of importing directly from
scheduler internals.

Example:
    from src.scheduler import api as scheduler_api

    # Create a daily schedule
    schedule = scheduler_api.create_daily_schedule(
        user_id=user_id,
        lesson_id=lesson_id,
        time_str="07:30",
        session=session
    )
"""

from __future__ import annotations

from src.core.timezone import datetime
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from src.models.database import Schedule


def create_daily_schedule(
    user_id: int,
    lesson_id: Optional[int],
    time_str: str,
    schedule_type: str = "daily",
    session: Optional[Session] = None,
) -> Schedule:
    """
    Create a daily schedule for lesson delivery.

    Args:
        user_id: The user ID to create the schedule for
        lesson_id: Optional lesson ID to associate with the schedule
        time_str: Time string in format "HH:MM" (e.g., "07:30")
        schedule_type: Type of schedule (default: "daily")
        session: Optional database session (will create one if not provided)

    Returns:
        The created Schedule object
    """
    from . import operations as scheduler_operations

    return scheduler_operations.create_daily_schedule(
        user_id=user_id,
        lesson_id=lesson_id,
        time_str=time_str,
        schedule_type=schedule_type,
        session=session,
    )


def update_daily_schedule(
    schedule_id: int,
    time_str: str,
    session: Optional[Session] = None,
) -> Optional[Schedule]:
    """
    Update an existing daily schedule's time.

    Args:
        schedule_id: The schedule ID to update
        time_str: New time string in format "HH:MM" (e.g., "08:00")
        session: Optional database session (will create one if not provided)

    Returns:
        The updated Schedule object, or None if not found
    """
    from . import operations as scheduler_operations

    return scheduler_operations.update_daily_schedule(
        schedule_id=schedule_id,
        time_str=time_str,
        session=session,
    )


def create_one_time_schedule(
    user_id: int,
    run_at: datetime,
    message: str,
    session: Optional[Session] = None,
) -> Schedule:
    """
    Create a one-time reminder schedule.

    Args:
        user_id: The user ID to create the reminder for
        run_at: When to send the reminder (datetime)
        message: The reminder message
        session: Optional database session (will create one if not provided)

    Returns:
        The created Schedule object
    """
    from . import operations as scheduler_operations

    return scheduler_operations.create_one_time_schedule(
        user_id=user_id,
        run_at=run_at,
        message=message,
        session=session,
    )


def deactivate_schedule(
    schedule_id: int,
    session: Optional[Session] = None,
) -> bool:
    """
    Deactivate a schedule and remove from APScheduler.

    Args:
        schedule_id: The schedule ID to deactivate
        session: Optional database session (will create one if not provided)

    Returns:
        True if the schedule was deactivated, False if not found/already inactive
    """
    from . import operations as scheduler_operations

    scheduler_operations.deactivate_schedule(schedule_id)
    return True


def deactivate_user_schedules(
    user_id: int,
    active_only: bool = True,
    session: Optional[Session] = None,
) -> int:
    """
    Deactivate all schedules for a user.

    Args:
        user_id: The user ID to deactivate schedules for
        active_only: If True, only deactivate active schedules
        session: Optional database session (will create one if not provided)

    Returns:
        Number of schedules deactivated
    """
    from . import operations as scheduler_operations

    return scheduler_operations.deactivate_user_schedules(
        user_id=user_id,
        active_only=active_only,
        session=session,
    )


def deactivate_user_schedules_by_type(
    user_id: int,
    schedule_type: str,
    active_only: bool = True,
    session: Optional[Session] = None,
) -> int:
    """
    Deactivate schedules filtered by type (one_time or daily).

    Args:
        user_id: The user ID to deactivate schedules for
        schedule_type: Type filter - 'one_time' or 'daily'
        active_only: If True, only deactivate active schedules
        session: Optional database session (will create one if not provided)

    Returns:
        Number of schedules deactivated
    """
    from . import manager as schedule_manager

    return schedule_manager.deactivate_user_schedules_by_type(
        user_id=user_id,
        schedule_type=schedule_type,
        active_only=active_only,
        session=session,
    )


def get_user_schedules(
    user_id: int,
    active_only: bool = True,
    session: Optional[Session] = None,
) -> List[Schedule]:
    """
    Get all schedules for a user.

    Args:
        user_id: The user ID to get schedules for
        active_only: If True, only return active schedules
        session: Optional database session (will create one if not provided)

    Returns:
        List of Schedule objects
    """
    from src.models.database import get_session

    from . import manager as schedule_manager

    with get_session(session) as s:
        return schedule_manager.get_user_schedules(
            user_id=user_id,
            session=s,
            active_only=active_only,
        )


def find_active_daily_schedule(
    user_id: int,
    session: Optional[Session] = None,
) -> Optional[Schedule]:
    """
    Find the active daily schedule for a user.

    Args:
        user_id: The user ID to find the schedule for
        session: Optional database session (will create one if not provided)

    Returns:
        The active daily Schedule, or None if not found
    """
    from . import manager as schedule_manager

    return schedule_manager.find_active_daily_schedule(
        user_id=user_id,
        session=session,
    )


def find_existing_one_time_reminder(
    user_id: int,
    run_at: datetime,
    session: Optional[Session] = None,
    tolerance_seconds: int = 60,
) -> Optional[Schedule]:
    """
    Check if user already has an active one-time reminder at approximately the same time.

    Args:
        user_id: The user ID
        run_at: The target datetime to check
        session: Optional database session
        tolerance_seconds: Time tolerance for matching (default 60 seconds)

    Returns:
        Existing Schedule if found, None otherwise
    """
    from . import manager as schedule_manager

    return schedule_manager.find_existing_one_time_reminder(
        user_id=user_id,
        run_at=run_at,
        session=session,
        tolerance_seconds=tolerance_seconds,
    )


def build_schedule_status_response(
    schedules: List[Schedule],
    tz_name: str = "UTC",
) -> str:
    """
    Build a human-readable status response for a list of schedules.

    Args:
        schedules: List of Schedule objects
        tz_name: Timezone name for display (e.g., "Europe/Oslo")

    Returns:
        Human-readable status message
    """
    from .schedule_query_handler import build_schedule_status_response as _build_response

    return _build_response(schedules, tz_name)


def parse_time_string(time_str: str) -> tuple[int, int]:
    """
    Parse a time string into hour and minute.

    Args:
        time_str: Time string (e.g., "07:30", "7:30 AM", "morning")

    Returns:
        Tuple of (hour, minute)
    """
    from .time_utils import parse_time_string as _parse_time

    return _parse_time(time_str)


def execute_scheduled_task(
    schedule_id: int,
    simulate: bool = False,
    session: Optional[Session] = None,
) -> Any:
    """
    Execute a scheduled task immediately.

    Args:
        schedule_id: The schedule ID to execute
        simulate: If True, simulate execution without sending messages
        session: Optional database session

    Returns:
        Execution result (list of messages or None)
    """
    from . import execution as scheduler_execution

    return scheduler_execution.execute_scheduled_task(
        schedule_id=schedule_id,
        simulate=simulate,
        session=session,
    )
