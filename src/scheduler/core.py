"""
Scheduler Service - Manage automated reminders and lesson delivery.

Uses APScheduler for reliable background job scheduling.
Supports:
- Daily lesson delivery
- Custom time-based reminders
- Interval-based reminders
- Multi-purpose scheduling
"""

from __future__ import annotations

from src.core.timezone import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from src.memories import MemoryManager
from src.models.database import Schedule, User

from . import execution as scheduler_execution
from . import lifecycle as scheduler_lifecycle
from . import operations as scheduler_operations
from .domain import SCHEDULE_TYPE_DAILY
from .time_utils import parse_time_string as _parse_time_string


class SchedulerService:
    """Manages background scheduling for lessons and reminders."""

    @staticmethod
    def _parse_lesson_int(value) -> int | None:
        from src.lessons.delivery import _parse_lesson_int

        return _parse_lesson_int(value)

    @staticmethod
    def _preview_build_for_no_last_sent(
        db: Session,
        memory_manager: MemoryManager,
        user_id: int,
        language: str,
    ) -> str | None:
        from src.lessons.delivery import build_lesson_preview

        return build_lesson_preview(db, memory_manager, user_id, language)

    @staticmethod
    def _build_schedule_message(
        db: Session,
        schedule: Schedule,
        memory_manager: MemoryManager,
    ) -> str | None:
        from src.scheduler.execution import _build_schedule_message

        return _build_schedule_message(db, schedule, memory_manager)

    @staticmethod
    def run_recovery_check() -> int:
        return scheduler_execution.run_recovery_check(get_scheduler_fn=SchedulerService.get_scheduler)

    @staticmethod
    def init_scheduler():
        return scheduler_lifecycle.init_scheduler()

    @staticmethod
    def shutdown():
        return scheduler_lifecycle.shutdown_scheduler()

    @staticmethod
    def get_scheduler() -> BackgroundScheduler:
        return scheduler_lifecycle.get_scheduler()

    @staticmethod
    def parse_time_string(time_str: str) -> tuple[int, int]:
        return _parse_time_string(time_str)

    @staticmethod
    def create_daily_schedule(
        user_id: int,
        lesson_id: int | None,
        time_str: str,
        schedule_type: str = SCHEDULE_TYPE_DAILY,
        session: Session | None = None,
    ) -> Schedule:
        return scheduler_operations.create_daily_schedule(
            user_id=user_id,
            lesson_id=lesson_id,
            time_str=time_str,
            schedule_type=schedule_type,
            session=session,
        )

    @staticmethod
    def update_daily_schedule(
        schedule_id: int,
        time_str: str,
        session: Session | None = None,
    ) -> Schedule | None:
        return scheduler_operations.update_daily_schedule(
            schedule_id=schedule_id,
            time_str=time_str,
            session=session,
        )

    @staticmethod
    def create_one_time_schedule(
        user_id: int,
        run_at: datetime,
        message: str,
        session: Session | None = None,
    ) -> Schedule:
        return scheduler_operations.create_one_time_schedule(
            user_id=user_id,
            run_at=run_at,
            message=message,
            session=session,
        )

    @staticmethod
    def execute_scheduled_task(
        schedule_id: int,
        simulate: bool = False,
        session: Session | None = None,
    ):
        return scheduler_execution.execute_scheduled_task(
            schedule_id=schedule_id,
            simulate=simulate,
            session=session,
        )

    @staticmethod
    def _execute_one_time_schedule(
        db: Session,
        schedule: Schedule,
        user: User,
        memory_manager: MemoryManager,
        simulate: bool,
    ) -> list:
        return scheduler_execution._execute_one_time_schedule(
            db=db,
            schedule=schedule,
            user=user,
            memory_manager=memory_manager,
            simulate=simulate,
        )

    @staticmethod
    def _execute_lesson_schedule(
        db: Session,
        schedule: Schedule,
        user: User,
        memory_manager: MemoryManager,
        simulate: bool,
    ) -> list:
        return scheduler_execution._execute_lesson_schedule(
            db=db,
            schedule=schedule,
            user=user,
            memory_manager=memory_manager,
            simulate=simulate,
        )

    @staticmethod
    def get_user_schedules(user_id: int, active_only: bool = True) -> list:
        return scheduler_operations.get_user_schedules(user_id, active_only=active_only)

    @staticmethod
    def deactivate_user_schedules(
        user_id: int,
        active_only: bool = True,
        session: Session | None = None,
    ) -> int:
        return scheduler_operations.deactivate_user_schedules(
            user_id=user_id,
            active_only=active_only,
            session=session,
        )

    @staticmethod
    def deactivate_user_schedules_by_type(
        user_id: int,
        schedule_type: str,
        active_only: bool = True,
        session: Session | None = None,
    ) -> int:
        """Deactivate schedules filtered by type (one_time or daily)."""
        from . import manager as schedule_manager

        return schedule_manager.deactivate_user_schedules_by_type(
            user_id=user_id,
            schedule_type=schedule_type,
            active_only=active_only,
            session=session,
        )

    @staticmethod
    def deactivate_schedule(schedule_id: int):
        return scheduler_operations.deactivate_schedule(schedule_id)
