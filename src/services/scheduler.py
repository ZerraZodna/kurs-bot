"""
Scheduler Service - Manage automated reminders and lesson delivery

Uses APScheduler for reliable background job scheduling.
Supports:
- Daily lesson delivery
- Custom time-based reminders
- Interval-based reminders
- Multi-purpose scheduling
"""

import asyncio
import json
from typing import Optional
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy.orm import Session
from src.models.database import SessionLocal, Schedule, User, Lesson, MessageLog
from src.services.memory_manager import MemoryManager
from src.config import settings
from src.integrations.telegram import send_message
import logging
import httpx

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: Optional[BackgroundScheduler] = None


class SchedulerService:
    """Manages background scheduling for lessons and reminders."""
    
    @staticmethod
    def init_scheduler():
        """Initialize the APScheduler background scheduler."""
        global _scheduler
        
        if _scheduler is not None:
            logger.warning("Scheduler already initialized")
            return _scheduler
        
        # Configure job store (stores jobs in database)
        jobstores = {
            'default': SQLAlchemyJobStore(url=settings.DATABASE_URL, tablename='apscheduler_jobs')
        }
        
        # Create scheduler
        _scheduler = BackgroundScheduler(
            jobstores=jobstores,
            timezone='UTC'
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
        """
        Parse time string to (hour, minute).
        
        Args:
            time_str: Time like "9:00 AM", "14:30", "morning", "evening"
        
        Returns:
            Tuple of (hour, minute) in 24-hour format
        """
        time_str = time_str.lower().strip()
        
        # Handle named times
        named_times = {
            "morning": (9, 0),
            "afternoon": (14, 0),
            "evening": (19, 0),
            "night": (21, 0),
            "morgenen": (9, 0),  # Norwegian
            "ettermiddagen": (14, 0),
            "kvelden": (19, 0),
        }
        
        if time_str in named_times:
            return named_times[time_str]
        
        # Parse "9:00 AM" or "14:30" format
        try:
            # Remove spaces
            time_str = time_str.replace(" ", "")
            
            # Handle AM/PM
            is_pm = "pm" in time_str
            is_am = "am" in time_str
            time_str = time_str.replace("am", "").replace("pm", "")
            
            # Split by colon
            if ":" in time_str:
                hour_str, minute_str = time_str.split(":")
                hour = int(hour_str)
                minute = int(minute_str)
            else:
                hour = int(time_str)
                minute = 0
            
            # Convert to 24-hour if PM
            if is_pm and hour < 12:
                hour += 12
            elif is_am and hour == 12:
                hour = 0
            
            # Validate
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return (hour, minute)
        
        except (ValueError, IndexError):
            pass
        
        # Default to 9 AM if parsing fails
        logger.warning(f"Could not parse time '{time_str}', defaulting to 9:00 AM")
        return (9, 0)
    
    @staticmethod
    def create_daily_schedule(
        user_id: int,
        lesson_id: Optional[int],
        time_str: str,
        schedule_type: str = "daily",
        session: Optional[Session] = None
    ) -> Schedule:
        """
        Create a daily schedule for lesson delivery.
        
        Args:
            user_id: User ID
            lesson_id: Lesson ID (optional for generic reminders)
            time_str: Time string (e.g., "9:00 AM", "morning")
            schedule_type: Type of schedule (daily, weekly, etc.)
            session: Database session
        
        Returns:
            Created Schedule object
        """
        close_session = False
        if session is None:
            session = SessionLocal()
            close_session = True
        
        try:
            # Parse time
            hour, minute = SchedulerService.parse_time_string(time_str)
            
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
                trigger=CronTrigger.from_crontab(cron_expression, timezone='UTC'),
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
        
        Args:
            schedule_id: The schedule ID to execute
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
                message = SchedulerService._get_schedule_message(memory_manager, schedule.user_id, schedule.schedule_id)
                if not message:
                    message = "Reminder"
                SchedulerService._send_outbound_message(db, user, message)

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
            language = SchedulerService._get_user_language(memory_manager, schedule.user_id)

            # If a confirmation is already pending, remind the user
            pending = SchedulerService._get_pending_confirmation(memory_manager, schedule.user_id)
            if pending:
                lesson_id = pending.get("lesson_id")
                next_id = pending.get("next_lesson_id")
                prompt = SchedulerService._build_confirmation_prompt(lesson_id, next_id, language)
                SchedulerService._send_outbound_message(db, user, prompt)
            else:
                # If no lesson has been sent yet, send Lesson 1 immediately
                last_sent = SchedulerService._get_last_sent_lesson_id(memory_manager, schedule.user_id)
                if not last_sent:
                    lesson = db.query(Lesson).filter(Lesson.lesson_id == 1).first()
                    if lesson:
                        message = SchedulerService._format_lesson_message(lesson, language)
                        SchedulerService._send_outbound_message(db, user, message)
                        SchedulerService._set_last_sent_lesson_id(memory_manager, schedule.user_id, 1)
                else:
                    # Ask if yesterday's lesson was completed before proceeding
                    next_id = (last_sent % 365) + 1
                    SchedulerService._set_pending_confirmation(memory_manager, schedule.user_id, last_sent, next_id)
                    prompt = SchedulerService._build_confirmation_prompt(last_sent, next_id, language)
                    SchedulerService._send_outbound_message(db, user, prompt)
            
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
    def _get_schedule_message(memory_manager: MemoryManager, user_id: int, schedule_id: int) -> Optional[str]:
        memories = memory_manager.get_memory(user_id=user_id, key="schedule_message")
        for memory in memories:
            try:
                data = json.loads(memory.get("value", ""))
                if data.get("schedule_id") == schedule_id:
                    return data.get("message")
            except Exception:
                continue
        return None

    @staticmethod
    def _get_user_language(memory_manager: MemoryManager, user_id: int) -> str:
        memories = memory_manager.get_memory(user_id, "user_language")
        return memories[0].get("value", "English") if memories else "English"

    @staticmethod
    def _get_last_sent_lesson_id(memory_manager: MemoryManager, user_id: int) -> Optional[int]:
        memories = memory_manager.get_memory(user_id, "last_sent_lesson_id")
        if not memories:
            return None
        value = str(memories[0].get("value", "")).strip()
        try:
            return int(value)
        except ValueError:
            return None

    @staticmethod
    def _set_last_sent_lesson_id(memory_manager: MemoryManager, user_id: int, lesson_id: int) -> None:
        memory_manager.store_memory(
            user_id=user_id,
            key="last_sent_lesson_id",
            value=str(lesson_id),
            category="progress",
            source="scheduler",
        )

    @staticmethod
    def _get_pending_confirmation(memory_manager: MemoryManager, user_id: int) -> Optional[dict]:
        memories = memory_manager.get_memory(user_id, "lesson_confirmation_pending")
        if not memories:
            return None
        def _normalize_dt(value: Optional[datetime]) -> datetime:
            if isinstance(value, datetime):
                return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
            return datetime.min.replace(tzinfo=timezone.utc)

        latest = max(memories, key=lambda m: _normalize_dt(m.get("created_at")))
        raw = latest.get("value", "")
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("lesson_id"):
                return data
        except Exception:
            return None
        return None

    @staticmethod
    def _set_pending_confirmation(
        memory_manager: MemoryManager,
        user_id: int,
        lesson_id: int,
        next_lesson_id: int,
    ) -> None:
        payload = json.dumps({"lesson_id": lesson_id, "next_lesson_id": next_lesson_id})
        memory_manager.store_memory(
            user_id=user_id,
            key="lesson_confirmation_pending",
            value=payload,
            category="conversation",
            ttl_hours=24,
            source="scheduler",
        )

    @staticmethod
    def _build_confirmation_prompt(lesson_id: int, next_id: int, language: str) -> str:
        base = (
            f"Did you complete Lesson {lesson_id} yesterday? "
            f"Reply yes to receive Lesson {next_id}."
        )
        if language.lower() in ["english", "en"]:
            return base
        return SchedulerService._translate_text_sync(base, language)

    @staticmethod
    def _format_lesson_message(lesson: Lesson, language: str) -> str:
        text = f"Lesson {lesson.lesson_id}: {lesson.title}\n\n{lesson.content}"
        if language.lower() in ["english", "en"]:
            return text
        return SchedulerService._translate_text_sync(text, language)

    @staticmethod
    def _translate_text_sync(text: str, language: str) -> str:
        try:
            prompt = (
                f"Translate the following text to {language}. "
                "Preserve paragraph breaks and meaning. Return only the translation.\n\n"
                f"{text}"
            )
            payload = {
                "model": settings.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
            }
            r = httpx.post(settings.OLLAMA_URL, json=payload, timeout=60.0)
            r.raise_for_status()
            data = r.json()
            return data.get("response", text) or text
        except Exception as e:
            logger.warning(f"Translation failed, sending original text: {e}")
            return text

    @staticmethod
    def _send_outbound_message(db: Session, user: User, text: str) -> None:
        status = "sent"
        error = None
        try:
            if user.channel == "telegram":
                asyncio.run(send_message(int(user.external_id), text))
            else:
                logger.warning(f"Unsupported channel for scheduled send: {user.channel}")
                status = "failed"
        except Exception as e:
            status = "failed"
            error = str(e)
            logger.error(f"Error sending scheduled message: {e}")

        # Log outbound message
        log = MessageLog(
            user_id=user.user_id,
            direction="outbound",
            channel=user.channel,
            external_message_id=None,
            content=text,
            status=status,
            error_message=error,
        )
        try:
            log.message_role = "assistant"
        except Exception:
            pass
        db.add(log)
        db.commit()
    
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

