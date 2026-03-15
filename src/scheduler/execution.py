"""Scheduler execution/recovery helpers.

Contains schedule execution paths and missed-job recovery behavior.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from sqlalchemy.orm import Session

from src.memories import MemoryManager
from src.models.database import Lesson, Schedule, User, get_session
from src.scheduler.message_utils import send_outbound_message

from .domain import is_one_time_schedule_type, job_id_for_schedule
from .memory_helpers import get_schedule_message, get_user_language
from src.lessons import format_lesson_message
from src.lessons.delivery import get_lesson_or_import, build_lesson_preview, deliver_lesson

logger = logging.getLogger(__name__)


def _parse_lesson_int(value) -> Optional[int]:
    """Safely parse a lesson id to int without using exceptions."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s.isdigit():
            return int(s)
    return None


def _load_lesson(db: Session, lesson_id: int) -> Optional[Lesson]:
    """Delegates to lessons.delivery.get_lesson_or_import."""
    return get_lesson_or_import(db, lesson_id)

def _build_schedule_message(
    db: Session,
    schedule: Schedule,
    memory_manager: MemoryManager,
) -> Optional[str]:
    """Build the outbound message for a schedule (without sending)."""
    if is_one_time_schedule_type(schedule.schedule_type):
        message = get_schedule_message(memory_manager, schedule.user_id, schedule.schedule_id)
        return message or "Reminder"

    language = get_user_language(memory_manager, schedule.user_id)

    from src.lessons.state import get_current_lesson
    
    last_sent = get_current_lesson(memory_manager, schedule.user_id)
    if not last_sent:
        return build_lesson_preview(db, memory_manager, schedule.user_id, language)

    next_id = (last_sent % 365) + 1
    # Always auto-advance without asking for confirmation
    lesson = get_lesson_or_import(db, next_id)
    if lesson:
        return format_lesson_message(lesson, language)

    # No lesson to send
    # Send a failure message?
    return None


def run_recovery_check(
    get_scheduler_fn: Optional[Callable[[], object]] = None,
) -> int:
    """Send any missed schedules and update their state."""
    if get_scheduler_fn is None:
        from .lifecycle import get_scheduler as get_scheduler_fn

    with get_session() as db:
        recovered = 0
        try:
            now = datetime.now(timezone.utc)
            due = (
                db.query(Schedule)
                .filter(
                    Schedule.is_active == True,
                    Schedule.next_send_time != None,
                    Schedule.next_send_time <= now,
                )
                .all()
            )
            if not due:
                return 0

            # For one-time reminders, only send the latest per user
            latest_one_time = {}
            to_deactivate = []
            ready = []
            for schedule in due:
                if is_one_time_schedule_type(schedule.schedule_type):
                    existing = latest_one_time.get(schedule.user_id)
                    if not existing:
                        latest_one_time[schedule.user_id] = schedule
                    else:
                        if (schedule.next_send_time or now) > (existing.next_send_time or now):
                            to_deactivate.append(existing)
                            latest_one_time[schedule.user_id] = schedule
                        else:
                            to_deactivate.append(schedule)
                else:
                    ready.append(schedule)

            ready.extend(latest_one_time.values())

            for schedule in to_deactivate:
                schedule.is_active = False
                schedule.next_send_time = None
                schedule.last_sent_at = now
                try:
                    from . import jobs as schedule_jobs
                    schedule_jobs.remove_job_for_schedule(schedule.schedule_id)
                except Exception as e:
                    logger.warning("Could not remove job %s: %s", job_id_for_schedule(schedule.schedule_id), e)

            if to_deactivate:
                db.commit()

            memory_manager = MemoryManager(db)
            apology = "Sorry I was not able to send this on time, due to down time of the server."
            for schedule in ready:
                user = db.query(User).filter_by(user_id=schedule.user_id).first()
                if not user:
                    continue
                message = _build_schedule_message(db, schedule, memory_manager)
                if not message:
                    continue

                message = f"{message}\n\n{apology}"
                send_outbound_message(db, user, message)

                if is_one_time_schedule_type(schedule.schedule_type):
                    schedule.last_sent_at = now
                    schedule.next_send_time = None
                    schedule.is_active = False
                    try:
                        from . import jobs as schedule_jobs

                        schedule_jobs.remove_job_for_schedule(schedule.schedule_id)
                    except Exception as e:
                        logger.warning("Could not remove job %s: %s", job_id_for_schedule(schedule.schedule_id), e)
                else:
                    schedule.next_send_time = schedule.last_sent_at + timedelta(days=1)
                    schedule.last_sent_at = now

                db.commit()
                recovered += 1
        except Exception as e:
            logger.error("Recovery check failed: %s", e)
            db.rollback()
        return recovered


def execute_scheduled_task(schedule_id: int, simulate: bool = False, session: Optional[Session] = None):
    """Execute a scheduled task (send lesson or reminder).

    This is called by APScheduler when a job triggers.

    `simulate=True` is used by debug "next_day" flows to simulate that a
    day boundary has happened. It is not a dry-run flag: outbound sends and
    memory updates may still occur. It primarily avoids schedule timestamp
    progression/commits in this method.
    """
    with get_session(session) as db:
        messages: list = []

        # Lookup schedule and user; if missing, close session and return
        schedule = db.query(Schedule).filter_by(schedule_id=schedule_id).first()
        if not schedule or not schedule.is_active:
            logger.warning("Schedule %s not found or inactive", schedule_id)
            return

        user = db.query(User).filter_by(user_id=schedule.user_id).first()
        if not user:
            logger.error("User %s not found for schedule %s", schedule.user_id, schedule_id)
            return

    logger.info("Executing schedule %s for user %s", schedule_id, schedule.user_id)

    memory_manager = MemoryManager(db)

    # One-time reminders are handled separately
    if is_one_time_schedule_type(schedule.schedule_type):
        messages = _execute_one_time_schedule(db, schedule, user, memory_manager, simulate)
        if simulate:
            return messages
        return

    # Otherwise handle lesson schedule
    messages = _execute_lesson_schedule(db, schedule, user, memory_manager, simulate)

    # For recurring lesson schedules, update next_send_time and last_sent
    if not simulate:
        now = datetime.now(timezone.utc)
        schedule.last_sent_at = now
        schedule.next_send_time = now + timedelta(days=1)
        user.last_active_at = now
        db.commit()
        logger.info("✓ Executed schedule %s, next send at %s", schedule_id, schedule.next_send_time)
    else:
        logger.info("Simulated execution of schedule %s (no DB changes)", schedule_id)

    if simulate:
        return messages


def _execute_one_time_schedule(
    db: Session,
    schedule: Schedule,
    user: User,
    memory_manager: MemoryManager,
    simulate: bool,
) -> list:
    """Handle a one-time reminder schedule execution.

    Returns list of messages produced during simulation.
    """
    messages: list = []
    message = get_schedule_message(memory_manager, schedule.user_id, schedule.schedule_id)
    if not message:
        message = "Reminder"
    send_outbound_message(db, user, message)
    if simulate:
        messages.append(message)
        logger.info("Simulated one-time reminder %s (no DB changes)", schedule.schedule_id)
        return messages

    # Persist state for executed one-time reminder
    schedule.last_sent_at = datetime.now(timezone.utc)
    schedule.next_send_time = None
    schedule.is_active = False
    db.commit()

    # Remove job from scheduler (use jobs helper)
    try:
        from . import jobs as schedule_jobs

        schedule_jobs.remove_job_for_schedule(schedule.schedule_id)
    except Exception as e:
        logger.warning("Could not remove job %s: %s", job_id_for_schedule(schedule.schedule_id), e)

    logger.info("✓ Executed one-time reminder %s", schedule.schedule_id)
    return messages


def _execute_lesson_schedule(
    db: Session,
    schedule: Schedule,
    user: User,
    memory_manager: MemoryManager,
    simulate: bool,
) -> list:
    """Handle recurring lesson schedule execution. Returns messages for simulation."""
    messages: list = []
    language = get_user_language(memory_manager, schedule.user_id)

    from src.lessons.state import compute_current_lesson_state

    state = compute_current_lesson_state(memory_manager, schedule.user_id)
    logger.debug(
        "Lesson state for user %s before delivery: lesson_id=%s advanced_by_day=%s previous_lesson_id=%s",
        schedule.user_id,
        state.get("lesson_id"),
        state.get("advanced_by_day"),
        state.get("previous_lesson_id"),
    )

    messages = deliver_lesson(db, schedule.user_id, None, memory_manager, simulate, language)
    return messages
