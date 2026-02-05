"""
Scheduler Service - Manage automated reminders and lesson delivery.

Uses APScheduler for reliable background job scheduling.
Supports:
- Daily lesson delivery
- Custom time-based reminders
- Interval-based reminders
- Multi-purpose scheduling
"""

import json
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy.orm import Session

from src.models.database import SessionLocal, Schedule, User, Lesson
from src.services.memory_manager import MemoryManager
from src.config import settings
from .time_utils import parse_time_string
from .memory_utils import (
    get_schedule_message,
    get_user_language,
    get_last_sent_lesson_id,
    set_last_sent_lesson_id,
    get_pending_confirmation,
    set_pending_confirmation,
)
from .message_utils import (
    build_confirmation_prompt,
    format_lesson_message,
    send_outbound_message,
)

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: Optional[BackgroundScheduler] = None


class SchedulerService:
    """Manages background scheduling for lessons and reminders."""

    @staticmethod
    def _build_schedule_message(
        db: Session,
        schedule: Schedule,
        memory_manager: MemoryManager,
    ) -> Optional[str]:
        """Build the outbound message for a schedule (without sending)."""
        if schedule.schedule_type.startswith("one_time"):
            message = get_schedule_message(memory_manager, schedule.user_id, schedule.schedule_id)
            return message or "Reminder"

        language = get_user_language(memory_manager, schedule.user_id)
        pending = get_pending_confirmation(memory_manager, schedule.user_id)
        if pending:
            lesson_id = pending.get("lesson_id")
            next_id = pending.get("next_lesson_id")
            return build_confirmation_prompt(lesson_id, next_id, language)

        last_sent = get_last_sent_lesson_id(memory_manager, schedule.user_id)
        if not last_sent:
            lesson = db.query(Lesson).filter(Lesson.lesson_id == 1).first()
            if lesson:
                set_last_sent_lesson_id(memory_manager, schedule.user_id, 1)
                return format_lesson_message(lesson, language)
            return None

        next_id = (last_sent % 365) + 1
        set_pending_confirmation(memory_manager, schedule.user_id, last_sent, next_id)
        return build_confirmation_prompt(last_sent, next_id, language)

    @staticmethod
    def run_recovery_check() -> int:
        """Send any missed schedules and update their state."""
        db = SessionLocal()
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
                if schedule.schedule_type.startswith("one_time"):
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

            scheduler = SchedulerService.get_scheduler()
            for schedule in to_deactivate:
                schedule.is_active = False
                schedule.next_send_time = None
                schedule.last_sent_at = now
                job_id = f"schedule_{schedule.schedule_id}"
                try:
                    scheduler.remove_job(job_id)
                except Exception as e:
                    logger.warning(f"Could not remove job {job_id}: {e}")

            if to_deactivate:
                db.commit()

            memory_manager = MemoryManager(db)
            apology = "Sorry I was not able to send this on time, due to down time of the server."
            for schedule in ready:
                user = db.query(User).filter_by(user_id=schedule.user_id).first()
                if not user:
                    continue
                message = SchedulerService._build_schedule_message(db, schedule, memory_manager)
                if not message:
                    continue
                message = f"{message}\n\n{apology}"
                send_outbound_message(db, user, message)

                if schedule.schedule_type.startswith("one_time"):
                    schedule.last_sent_at = now
                    schedule.next_send_time = None
                    schedule.is_active = False
                    job_id = f"schedule_{schedule.schedule_id}"
                    try:
                        scheduler.remove_job(job_id)
                    except Exception as e:
                        logger.warning(f"Could not remove job {job_id}: {e}")
                else:
                    schedule.last_sent_at = now
                    schedule.next_send_time = now + timedelta(days=1)

                db.commit()
                recovered += 1

            return recovered
        except Exception as e:
            logger.error("Recovery check failed: %s", e)
            db.rollback()
            return recovered
        finally:
            db.close()

    @staticmethod
    def init_scheduler():
        """Initialize the APScheduler background scheduler."""
        global _scheduler

        if _scheduler is not None:
            logger.warning("Scheduler already initialized")
            return _scheduler

        # Configure job store (stores jobs in database)
        jobstores = {
            "default": SQLAlchemyJobStore(url=settings.DATABASE_URL, tablename="apscheduler_jobs")
        }

        # Create scheduler
        _scheduler = BackgroundScheduler(
            jobstores=jobstores,
            timezone="UTC",
        )

        _scheduler.start()
        logger.info("✓ Scheduler initialized and started")

        return _scheduler

    @staticmethod
    def shutdown():
        """Shutdown the scheduler gracefully."""
        global _scheduler
        if _scheduler:
            _scheduler.shutdown(wait=True)
            _scheduler = None
            logger.info("✓ Scheduler shut down")

    @staticmethod
    def get_scheduler() -> BackgroundScheduler:
        """Get the scheduler instance, initializing if needed."""
        global _scheduler
        if _scheduler is None:
            return SchedulerService.init_scheduler()
        return _scheduler

    @staticmethod
    def parse_time_string(time_str: str) -> tuple[int, int]:
        return parse_time_string(time_str)

    @staticmethod
    def create_daily_schedule(
        user_id: int,
        lesson_id: Optional[int],
        time_str: str,
        schedule_type: str = "daily",
        session: Optional[Session] = None,
    ) -> Schedule:
        """
        Create a daily schedule for lesson delivery.
        """
        close_session = False
        if session is None:
            session = SessionLocal()
            close_session = True

        try:
            # Parse time
            hour, minute = parse_time_string(time_str)

            # Create cron expression for daily at specified time
            cron_expression = f"{minute} {hour} * * *"  # Every day at hour:minute

            # Calculate next send time
            now = datetime.now(timezone.utc)
            next_send = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # If time has passed today, schedule for tomorrow
            if next_send <= now:
                next_send += timedelta(days=1)

            # Create schedule record
            schedule = Schedule(
                user_id=user_id,
                lesson_id=lesson_id,
                schedule_type=schedule_type,
                cron_expression=cron_expression,
                next_send_time=next_send,
                is_active=True,
                created_at=now,
            )

            session.add(schedule)
            session.commit()

            # Add job to APScheduler
            scheduler = SchedulerService.get_scheduler()
            job_id = f"schedule_{schedule.schedule_id}"

            scheduler.add_job(
                func=SchedulerService.execute_scheduled_task,
                trigger=CronTrigger.from_crontab(cron_expression, timezone="UTC"),
                args=[schedule.schedule_id],
                id=job_id,
                replace_existing=True,
            )

            logger.info(f"✓ Created daily schedule for user {user_id} at {hour}:{minute:02d} UTC")

            return schedule

        finally:
            if close_session:
                session.close()

    @staticmethod
    def create_one_time_schedule(
        user_id: int,
        run_at: datetime,
        message: str,
        session: Optional[Session] = None,
    ) -> Schedule:
        """Create a one-time reminder schedule."""
        close_session = False
        if session is None:
            session = SessionLocal()
            close_session = True

        try:
            now = datetime.now(timezone.utc)
            run_at = run_at.astimezone(timezone.utc)

            schedule = Schedule(
                user_id=user_id,
                lesson_id=None,
                schedule_type="one_time_reminder",
                cron_expression=f"once:{run_at.isoformat()}",
                next_send_time=run_at,
                is_active=True,
                created_at=now,
            )

            session.add(schedule)
            session.commit()

            # Store reminder message
            memory_manager = MemoryManager(session)
            payload = json.dumps({"schedule_id": schedule.schedule_id, "message": message})
            memory_manager.store_memory(
                user_id=user_id,
                key="schedule_message",
                value=payload,
                category="conversation",
                ttl_hours=48,
                source="scheduler",
                allow_duplicates=True,
            )

            # Add job to APScheduler
            scheduler = SchedulerService.get_scheduler()
            job_id = f"schedule_{schedule.schedule_id}"
            scheduler.add_job(
                func=SchedulerService.execute_scheduled_task,
                trigger=DateTrigger(run_date=run_at, timezone="UTC"),
                args=[schedule.schedule_id],
                id=job_id,
                replace_existing=True,
            )

            logger.info(f"✓ Created one-time reminder for user {user_id} at {run_at.isoformat()}")

            return schedule

        finally:
            if close_session:
                session.close()

    @staticmethod
    def execute_scheduled_task(schedule_id: int):
        """
        Execute a scheduled task (send lesson or reminder).

        This is called by APScheduler when a job triggers.
        """
        db = SessionLocal()
        try:
            schedule = db.query(Schedule).filter_by(schedule_id=schedule_id).first()

            if not schedule or not schedule.is_active:
                logger.warning(f"Schedule {schedule_id} not found or inactive")
                return

            user = db.query(User).filter_by(user_id=schedule.user_id).first()
            if not user:
                logger.error(f"User {schedule.user_id} not found for schedule {schedule_id}")
                return

            logger.info(f"Executing schedule {schedule_id} for user {schedule.user_id}")

            memory_manager = MemoryManager(db)

            if schedule.schedule_type.startswith("one_time"):
                message = get_schedule_message(memory_manager, schedule.user_id, schedule.schedule_id)
                if not message:
                    message = "Reminder"
                send_outbound_message(db, user, message)

                schedule.last_sent_at = datetime.now(timezone.utc)
                schedule.next_send_time = None
                schedule.is_active = False
                db.commit()

                # Remove job from scheduler
                scheduler = SchedulerService.get_scheduler()
                job_id = f"schedule_{schedule.schedule_id}"
                try:
                    scheduler.remove_job(job_id)
                except Exception as e:
                    logger.warning(f"Could not remove job {job_id}: {e}")

                logger.info(f"✓ Executed one-time reminder {schedule_id}")
                return

            # Determine user's language (default English)
            language = get_user_language(memory_manager, schedule.user_id)

            # If a confirmation is already pending, remind the user
            pending = get_pending_confirmation(memory_manager, schedule.user_id)
            if pending:
                lesson_id = pending.get("lesson_id")
                next_id = pending.get("next_lesson_id")
                prompt = build_confirmation_prompt(lesson_id, next_id, language)
                send_outbound_message(db, user, prompt)
            else:
                # If no lesson has been sent yet, send Lesson 1 immediately
                last_sent = get_last_sent_lesson_id(memory_manager, schedule.user_id)
                if not last_sent:
                    lesson = db.query(Lesson).filter(Lesson.lesson_id == 1).first()
                    if lesson:
                        message = format_lesson_message(lesson, language)
                        send_outbound_message(db, user, message)
                        set_last_sent_lesson_id(memory_manager, schedule.user_id, 1)
                else:
                    # Ask if yesterday's lesson was completed before proceeding
                    next_id = (last_sent % 365) + 1
                    set_pending_confirmation(memory_manager, schedule.user_id, last_sent, next_id)
                    prompt = build_confirmation_prompt(last_sent, next_id, language)
                    send_outbound_message(db, user, prompt)

            # Update schedule
            schedule.last_sent_at = datetime.now(timezone.utc)

            # Calculate next send time
            now = datetime.now(timezone.utc)
            schedule.next_send_time = now + timedelta(days=1)

            db.commit()

            logger.info(f"✓ Executed schedule {schedule_id}, next send at {schedule.next_send_time}")

        except Exception as e:
            logger.error(f"Error executing schedule {schedule_id}: {e}")
            db.rollback()

        finally:
            db.close()

    @staticmethod
    def get_user_schedules(user_id: int, active_only: bool = True) -> list:
        """Get all schedules for a user."""
        db = SessionLocal()
        try:
            query = db.query(Schedule).filter_by(user_id=user_id)
            if active_only:
                query = query.filter_by(is_active=True)
            return query.all()
        finally:
            db.close()

    @staticmethod
    def deactivate_user_schedules(
        user_id: int,
        active_only: bool = True,
        session: Optional[Session] = None,
    ) -> int:
        """Deactivate all schedules for a user and remove their jobs."""
        close_session = False
        if session is None:
            session = SessionLocal()
            close_session = True
        try:
            query = session.query(Schedule).filter_by(user_id=user_id)
            if active_only:
                query = query.filter_by(is_active=True)
            schedules = query.all()
            if not schedules:
                return 0

            scheduler = SchedulerService.get_scheduler()
            for schedule in schedules:
                schedule.is_active = False
                job_id = f"schedule_{schedule.schedule_id}"
                try:
                    scheduler.remove_job(job_id)
                except Exception as e:
                    logger.warning(f"Could not remove job {job_id}: {e}")

            session.commit()
            logger.info(f"✓ Deactivated {len(schedules)} schedule(s) for user {user_id}")
            return len(schedules)
        finally:
            if close_session:
                session.close()

    @staticmethod
    def deactivate_schedule(schedule_id: int):
        """Deactivate a schedule and remove from APScheduler."""
        db = SessionLocal()
        try:
            schedule = db.query(Schedule).filter_by(schedule_id=schedule_id).first()
            if schedule:
                schedule.is_active = False
                db.commit()

                # Remove from APScheduler
                scheduler = SchedulerService.get_scheduler()
                job_id = f"schedule_{schedule_id}"
                try:
                    scheduler.remove_job(job_id)
                except Exception as e:
                    logger.warning(f"Could not remove job {job_id}: {e}")

                logger.info(f"✓ Deactivated schedule {schedule_id}")
        finally:
            db.close()
