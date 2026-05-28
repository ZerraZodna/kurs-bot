"""Manage practice reminder jobs for ACIM lessons.

Creates one-time reminder schedules based on lesson practice instructions.
Handles hourly, twice_daily, three_times_daily, and morning_evening patterns.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from src.core.timezone import utc_now
from src.memories import MemoryManager
from src.memories.constants import MemoryCategory, MemoryKey
from src.models.database import Schedule, get_session

from . import manager as schedule_manager
from . import jobs as schedule_jobs
from .domain import SCHEDULE_TYPE_ONE_TIME_REMINDER

logger = logging.getLogger(__name__)

DEFAULT_EVENING_CUTOFF = "22:00"
DEFAULT_REMINDER_EARLY_HOUR = 7
DEFAULT_REMINDER_LATE_HOUR = 22

# Default times for non-hourly patterns
DEFAULT_TIMES = {
    "twice_daily": ["09:00", "18:00"],
    "three_times_daily": ["09:00", "14:00", "19:00"],
    "morning_evening": ["09:00", "18:00"],
}


def _parse_evening_cutoff(time_str: str) -> int:
    """Parse a time string like '22:00' into an hour integer."""
    try:
        parts = time_str.strip().split(":")
        return int(parts[0])
    except (ValueError, IndexError):
        return DEFAULT_REMINDER_LATE_HOUR


def _format_reminder_message(key_phrase: str, instructions: str, practice_window: str) -> str:
    """Format a reminder message with key phrase and instructions."""
    parts = ["\U0001f550 Time to practice."]

    if key_phrase:
        parts.append("")
        parts.append(f'"{key_phrase}"')

    if instructions:
        parts.append("")
        parts.append(instructions)

    return "\n".join(parts)


def _get_evening_cutoff(session: Session, user_id: int) -> str:
    """Get user's evening cutoff preference, or default."""
    memory_manager = MemoryManager(session)
    cutoff_mem = memory_manager.get_memory(user_id, MemoryKey.PRACTICE_REMINDER_EVENING_CUTOFF)
    if cutoff_mem and cutoff_mem[0].get("value"):
        return str(cutoff_mem[0]["value"])
    return DEFAULT_EVENING_CUTOFF


def _generate_hourly_times(start_hour: int, end_hour: int) -> list[str]:
    """Generate hourly time strings from start_hour to end_hour."""
    times = []
    for h in range(start_hour, end_hour):
        times.append(f"{h:02d}:00")
    return times


def create_reminders(
    lesson_id: int,
    user_id: int,
    practice_instructions: dict[str, Any],
    session: Session | None = None,
) -> list[Schedule]:
    """Create practice reminder schedules based on lesson instructions.

    Args:
        lesson_id: The lesson to create reminders for
        user_id: The user to create reminders for
        practice_instructions: Extracted practice instructions dict
        session: Optional DB session (managed via context manager)

    Returns:
        List of created Schedule objects.
    """
    with get_session(session) as db:
        try:
            frequency = practice_instructions.get("frequency", "single")
            key_phrases = practice_instructions.get("key_phrases", [])
            instructions = practice_instructions.get("instructions", "")
            practice_window = practice_instructions.get("practice_window", "")

            if frequency == "single":
                logger.info("No reminders needed for lesson %d (frequency=single)", lesson_id)
                return []

            # Get evening cutoff preference
            evening_cutoff_str = _get_evening_cutoff(db, user_id)
            end_hour = _parse_evening_cutoff(evening_cutoff_str)

            # Determine reminder times based on frequency
            now = utc_now()
            reminder_times = []

            if frequency == "hourly":
                # Every hour from next full hour until evening cutoff
                start_hour = _parse_hour_from_time_str(practice_window) or DEFAULT_REMINDER_EARLY_HOUR
                reminder_times = _generate_hourly_times(start_hour, end_hour)
            elif frequency in ("twice_daily", "morning_evening"):
                default_times = DEFAULT_TIMES.get(frequency, ["09:00", "18:00"])
                reminder_times = default_times
            elif frequency == "three_times_daily":
                reminder_times = DEFAULT_TIMES.get("three_times_daily", ["09:00", "14:00", "19:00"])
            else:
                # Custom — try to parse from practice_window
                reminder_times = _parse_custom_times(
                    practice_window, DEFAULT_TIMES.get("twice_daily", ["09:00", "18:00"])
                )

            if not reminder_times:
                logger.info("No reminder times determined for lesson %d", lesson_id)
                return []

            # Filter out times that have already passed today
            current_hour = now.hour
            filtered_times = []
            for t in reminder_times:
                try:
                    h, m = map(int, t.split(":"))
                    if h > current_hour or (h == current_hour and m > now.minute):
                        filtered_times.append(t)
                except ValueError:
                    continue

            if not filtered_times:
                logger.info("All reminder times for lesson %d have passed", lesson_id)
                return []

            # Create one-time schedules for each reminder time
            created = []
            for time_str in filtered_times:
                schedule = _create_reminder_schedule(
                    user_id=user_id,
                    lesson_id=lesson_id,
                    time_str=time_str,
                    key_phrases=key_phrases,
                    instructions=instructions,
                    session=db,
                )
                if schedule:
                    created.append(schedule)

            logger.info(
                "Created %d reminder(s) for lesson %d (frequency=%s, times=%s)",
                len(created),
                lesson_id,
                frequency,
                filtered_times,
            )
            return created
        except Exception as e:
            logger.error("Failed to create reminders for lesson %d: %s", lesson_id, e)
            return []


def _create_reminder_schedule(
    user_id: int,
    lesson_id: int,
    time_str: str,
    key_phrases: list[str],
    instructions: str,
    session: Session,
) -> Schedule | None:
    """Create a single one-time reminder schedule."""
    # Parse time string
    try:
        h, m = map(int, time_str.split(":"))
    except (ValueError, IndexError):
        logger.warning("Invalid time string: %s", time_str)
        return None

    # Create datetime for today at the specified time
    now = utc_now()
    run_at = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if run_at <= now:
        # Time already passed today, skip
        return None

    # Format reminder message
    key_phrase = key_phrases[0] if key_phrases else ""
    message = _format_reminder_message(key_phrase, instructions, "")

    # Create schedule
    schedule = schedule_manager.create_schedule(
        user_id=user_id,
        lesson_id=lesson_id,
        schedule_type=SCHEDULE_TYPE_ONE_TIME_REMINDER,
        cron_expression=f"once:{run_at.isoformat()}",
        next_send_time=run_at,
        session=session,
    )

    # Store reminder message in memory
    memory_manager = MemoryManager(session)
    payload = json.dumps({
        "schedule_id": schedule.schedule_id,
        "message": message,
        "lesson_id": lesson_id,
    })
    memory_manager.store_memory(
        user_id=user_id,
        key=MemoryKey.SCHEDULE_MESSAGE,
        value=payload,
        category=MemoryCategory.CONVERSATION.value,
        ttl_hours=48,
        source="reminder_manager",
        allow_duplicates=True,
    )

    # Sync job to APScheduler
    try:
        schedule_jobs.sync_job_for_schedule(schedule)
    except Exception as e:
        logger.warning("Could not add reminder job for schedule %s: %s", schedule.schedule_id, e)

    return schedule


def stop_daily_reminders(user_id: int, session: Session | None = None) -> int:
    """Stop all active practice reminders for a user.

    Only affects one-time reminders that have a lesson_id (practice reminders).
    Does not affect general one-time reminders.

    Args:
        user_id: The user ID
        session: Optional DB session (managed via context manager)

    Returns:
        Number of reminders stopped.
    """
    with get_session(session) as db:
        try:
            # Find active one-time reminders that have a lesson_id (practice reminders)
            practice_reminders = (
                db
                .query(Schedule)
                .filter(
                    Schedule.user_id == user_id,
                    Schedule.is_active == True,
                    Schedule.schedule_type.like("one_time%"),
                    Schedule.lesson_id.isnot(None),
                )
                .all()
            )

            if not practice_reminders:
                return 0

            for schedule in practice_reminders:
                schedule.is_active = False
                db.add(schedule)

            db.commit()

            # Remove APScheduler jobs
            for schedule in practice_reminders:
                try:
                    schedule_jobs.remove_job_for_schedule(schedule.schedule_id)
                except Exception as e:
                    logger.warning("Could not remove job %s: %s", schedule.schedule_id, e)

            logger.info("Stopped %d practice reminder(s) for user %d", len(practice_reminders), user_id)

            # Clear pending state so the next lesson re-asks about reminders
            from src.memories import MemoryManager
            from src.models.database import get_session as get_db_session

            with get_db_session() as mem_db:
                mm = MemoryManager(mem_db)
                mm.store_memory(
                    user_id=user_id,
                    key=MemoryKey.PRACTICE_REMINDER_PENDING,
                    value="",
                    ttl_hours=1,
                    category=MemoryCategory.CONVERSATION.value,
                    source="reminder_manager",
                )

            return len(practice_reminders)
        except Exception as e:
            logger.error("Failed to stop reminders for user %d: %s", user_id, e)
            return 0


def _parse_hour_from_time_str(practice_window: str) -> int | None:
    """Try to extract the starting hour from a practice_window string."""
    if not practice_window:
        return None
    match = re.search(r"(\d{1,2}):00", practice_window)
    if match:
        return int(match.group(1))
    return None


def _parse_custom_times(practice_window: str, fallback: list[str]) -> list[str]:
    """Try to parse specific times from practice_window string."""
    if not practice_window:
        return fallback
    # Look for time patterns like "09:00", "14:00", etc.
    times = re.findall(r"(\d{1,2}:\d{2})", practice_window)
    if times:
        return times
    return fallback
