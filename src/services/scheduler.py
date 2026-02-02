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
from typing import Optional
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy.orm import Session
from src.models.database import SessionLocal, Schedule, User
from src.config import settings
import logging

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
            
            # TODO: Send the actual lesson/reminder via MessageRouter
            # For now, just log that we would send
            # This will be implemented when we integrate with lesson engine
            
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

