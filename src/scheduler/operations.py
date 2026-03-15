"""Scheduler CRUD/orchestration helpers.

Contains schedule create/update/deactivate flows and APScheduler sync wiring.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.memories import MemoryManager
from src.memories.constants import MemoryCategory, MemoryKey
from src.models.database import Schedule, User, get_session

from . import jobs as schedule_jobs
from . import manager as schedule_manager
from .domain import (
    SCHEDULE_TYPE_DAILY,
    SCHEDULE_TYPE_ONE_TIME_REMINDER,
    is_daily_schedule_family,
    job_id_for_schedule,
)
from .time_utils import parse_time_string
from src.core.timezone import get_user_timezone_from_db

logger = logging.getLogger(__name__)


def create_daily_schedule(
    user_id: int,
    lesson_id: Optional[int],
    time_str: str,
    schedule_type: str = SCHEDULE_TYPE_DAILY,
    session: Optional[Session] = None,
) -> Schedule:
    """Create a daily schedule for lesson delivery."""
    with get_session(session) as s:
        # Debug: trace schedule creation attempts
        logger.debug(
            f"create_daily_schedule called user={user_id} "
            f"time_str={time_str} ts={datetime.now(timezone.utc).isoformat()}"
        )
        # Compute next send time and cron expression for the user's timezone
        tz_name = get_user_timezone_from_db(s, user_id)

        from .time_utils import compute_next_send_and_cron

        next_send, cron_expression = compute_next_send_and_cron(time_str, tz_name)

        # Create schedule record
        # Persist using manager and then sync APScheduler job
        schedule = schedule_manager.create_schedule(
            user_id=user_id,
            lesson_id=lesson_id,
            schedule_type=schedule_type,
            cron_expression=cron_expression,
            next_send_time=next_send,
            session=s,
        )

        created_at = getattr(schedule, "created_at", None)
        created_str = (
            created_at.isoformat()
            if created_at is not None
            else __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        )
        logger.debug(
            f"persisted schedule id=<{getattr(schedule, 'schedule_id', None)}> "
            f"user={user_id} next_send_local_input={next_send.isoformat()} "
            f"cron='{cron_expression}' created_at={created_str}"
        )
        # Log the actual stored DB value for next_send_time (UTC-aware expected)
        stored_ns = getattr(schedule, "next_send_time", None)
        if stored_ns is not None:
            logger.info(
                "Stored next_send_time (iso): %s, tzinfo=%s",
                stored_ns.isoformat(),
                getattr(stored_ns, "tzinfo", None),
            )

        # Sync job to APScheduler
        try:
            schedule_jobs.sync_job_for_schedule(schedule)
        except Exception as e:
            logger.warning(
                "Could not add job for schedule %s: %s",
                getattr(schedule, "schedule_id", None),
                e,
            )

        # For logging, parse the time string into hour/minute if available
        hour, minute = parse_time_string(time_str)

        logger.info("✓ Created daily schedule for user %s at %s:%02d (%s)", user_id, hour, minute, tz_name)

        return schedule


def update_daily_schedule(
    schedule_id: int,
    time_str: str,
    session: Optional[Session] = None,
) -> Optional[Schedule]:
    """Update an existing daily schedule in-place (cron_expression and next_send_time).

    This avoids creating duplicate Schedule rows when a user updates their
    default reminder time.
    """
    with get_session(session) as s:
        sched = s.query(Schedule).filter_by(schedule_id=schedule_id).first()
        if not sched:
            return None

        # Only support updating daily schedules
        if not is_daily_schedule_family(sched.schedule_type):
            return None

        # Compute new next_send and cron_expression using helper
        from .time_utils import compute_next_send_and_cron

        tz_name = get_user_timezone_from_db(s, sched.user_id)

        next_send, cron_expression = compute_next_send_and_cron(time_str, tz_name)

        updates = {
            "cron_expression": cron_expression,
            "next_send_time": next_send,
            "is_active": True,
        }
        updated = schedule_manager.update_schedule(schedule_id, updates, session=s)

        # Update APScheduler job (replace existing job)
        try:
            if updated:
                schedule_jobs.sync_job_for_schedule(updated)
        except Exception as e:
            logger.warning("Could not update job %s: %s", schedule_id, e)

        # Ensure hour/minute are defined for logging (may not exist if parse failed)
        hour, minute = parse_time_string(time_str)

        logger.info(
            "✓ Updated daily schedule %s for user %s to %s:%02d (%s)",
            schedule_id,
            getattr(updated, "user_id", "unknown"),
            hour,
            minute,
            tz_name,
        )
        stored_ns = getattr(updated, "next_send_time", None)
        if stored_ns is not None:
            logger.info(
                "Updated schedule stored next_send_time (iso): %s, tzinfo=%s",
                stored_ns.isoformat(),
                getattr(stored_ns, "tzinfo", None),
            )
        return updated


def create_one_time_schedule(
    user_id: int,
    run_at: datetime,
    message: str,
    session: Optional[Session] = None,
) -> Schedule:
    """Create a one-time reminder schedule."""
    with get_session(session) as s:
        now = datetime.now(timezone.utc)
        from src.core.timezone import to_utc

        run_at = to_utc(run_at)

        # Check for existing reminder at the same time (deduplication)
        existing = schedule_manager.find_existing_one_time_reminder(
            user_id=user_id,
            run_at=run_at,
            session=s,
            tolerance_seconds=60,
        )
        if existing:
            logger.info(
                "Duplicate one-time reminder detected for user %s at %s. Returning existing schedule %s.",
                user_id,
                run_at.isoformat(),
                existing.schedule_id,
            )
            return existing

        # Persist via manager
        schedule = schedule_manager.create_schedule(
            user_id=user_id,
            lesson_id=None,
            schedule_type=SCHEDULE_TYPE_ONE_TIME_REMINDER,
            cron_expression=f"once:{run_at.isoformat()}",
            next_send_time=run_at,
            session=s,
        )

        # Store reminder message
        memory_manager = MemoryManager(s)
        payload = json.dumps({"schedule_id": schedule.schedule_id, "message": message})
        memory_manager.store_memory(
            user_id=user_id,
            key=MemoryKey.SCHEDULE_MESSAGE,
            value=payload,
            category=MemoryCategory.CONVERSATION.value,
            ttl_hours=48,
            source="scheduler",
            allow_duplicates=True,
        )

        # Sync job to APScheduler
        try:
            schedule_jobs.sync_job_for_schedule(schedule)
        except Exception as e:
            logger.warning(
                "Could not add one-time job for schedule %s: %s",
                getattr(schedule, "schedule_id", None),
                e,
            )

        logger.info("✓ Created one-time reminder for user %s at %s", user_id, run_at.isoformat())

        return schedule


def get_user_schedules(user_id: int, active_only: bool = True, session: Optional[Session] = None) -> list:
    """Get all schedules for a user."""
    # Delegate to manager for pure-DB access
    with get_session(session) as s:
        return schedule_manager.get_user_schedules(user_id=user_id, session=s, active_only=active_only)


def deactivate_user_schedules(
    user_id: int,
    active_only: bool = True,
    session: Optional[Session] = None,
) -> int:
    """Deactivate all schedules for a user and remove their jobs."""
    with get_session(session) as s:
        from src.scheduler import deactivate_user_schedules_and_remove_jobs

        count = deactivate_user_schedules_and_remove_jobs(user_id=user_id, active_only=active_only, session=s)
        if count:
            logger.info("✓ Deactivated %s schedule(s) for user %s", count, user_id)
        return count


def deactivate_schedule(schedule_id: int) -> None:
    """Deactivate a schedule and remove from APScheduler."""
    # Delegate DB change to manager and remove job via jobs module
    try:
        changed = schedule_manager.deactivate_schedule(schedule_id)
        if changed:
            try:
                schedule_jobs.remove_job_for_schedule(schedule_id)
            except Exception as e:
                logger.warning("Could not remove job %s: %s", job_id_for_schedule(schedule_id), e)
            logger.info("✓ Deactivated schedule %s", schedule_id)
    except Exception:
        # Ensure we don't bubble DB exceptions here
        logger.exception("Error deactivating schedule %s", schedule_id)
