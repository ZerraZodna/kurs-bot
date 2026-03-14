"""Pure DB helpers for Schedule records.

This module contains functions that perform CRUD operations on the
`Schedule` model without interacting with APScheduler. It is intended to
be a thin, testable layer so the APScheduler wiring can live separately.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from src.models.database import SessionLocal, Schedule, get_session
from src.core.timezone import to_utc
from .domain import SCHEDULE_TYPE_DAILY


def create_schedule(
    user_id: int,
    lesson_id: Optional[int],
    schedule_type: str,
    cron_expression: str,
    next_send_time: Optional[datetime] = None,
    session=None,
) -> Schedule:
    now = datetime.now(timezone.utc)

    # Ensure next_send_time persisted as UTC-aware datetime
    if next_send_time is not None:
        next_send_time = to_utc(next_send_time)

    sched = Schedule(
        user_id=user_id,
        lesson_id=lesson_id,
        schedule_type=schedule_type,
        cron_expression=cron_expression,
        next_send_time=next_send_time,
        is_active=True,
        created_at=now,
    )
    session.add(sched)
    session.commit()
    session.refresh(sched)
    return sched


def update_schedule(schedule_id: int, updates: Dict[str, Any], session=None) -> Optional[Schedule]:
    """Apply safe updates to a schedule and return the updated object.

    Supported update keys: `cron_expression`, `next_send_time`, `is_active`, `lesson_id`.
    """
    with get_session(session) as s:
        sched = s.query(Schedule).filter_by(schedule_id=schedule_id).first()
        if not sched:
            return None

        allowed = {"cron_expression", "next_send_time", "is_active", "lesson_id"}
        changed = False
        for k, v in updates.items():
            if k in allowed:
                # Ensure next_send_time is stored in UTC if provided
                if k == "next_send_time" and v is not None:
                    v = to_utc(v)
                setattr(sched, k, v)
                changed = True

        if changed:
            s.add(sched)
            s.commit()
            s.refresh(sched)

        return sched


def deactivate_schedule(schedule_id: int, session=None) -> bool:
    """Mark a schedule inactive. Returns True if changed, False if not found/already inactive."""
    with get_session(session) as s:
        sched = s.query(Schedule).filter_by(schedule_id=schedule_id).first()
        if not sched or not sched.is_active:
            return False
        sched.is_active = False
        s.add(sched)
        s.commit()
        return True


def get_user_schedules(user_id: int, active_only: bool = True, session=None) -> List[Schedule]:
    with get_session(session) as s:
        query = s.query(Schedule).filter_by(user_id=user_id)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(Schedule.created_at).all()


def find_active_daily_schedule(user_id: int, session=None) -> Optional[Schedule]:
    with get_session(session) as s:
        return (
            s.query(Schedule)
            .filter_by(user_id=user_id, is_active=True, schedule_type=SCHEDULE_TYPE_DAILY)
            .order_by(Schedule.created_at)
            .first()
        )


def find_existing_one_time_reminder(
    user_id: int, 
    run_at: datetime, 
    session=None,
    tolerance_seconds: int = 60
) -> Optional[Schedule]:
    """Check if user already has an active one-time reminder at approximately the same time.
    
    Args:
        user_id: The user ID
        run_at: The target datetime to check
        session: Optional DB session
        tolerance_seconds: Time tolerance for matching (default 60 seconds)
    
    Returns:
        Existing Schedule if found, None otherwise
    """
    with get_session(session) as s:
        from .domain import is_one_time_schedule_type
        
        # Get all active schedules for user
        schedules = (
            s.query(Schedule)
            .filter_by(user_id=user_id, is_active=True)
            .all()
        )
        
        # Check for one-time reminders within tolerance
        for schedule in schedules:
            if not is_one_time_schedule_type(schedule.schedule_type):
                continue
            
            if schedule.next_send_time is None:
                continue
            
            # Calculate time difference
            time_diff = abs((schedule.next_send_time - run_at).total_seconds())
            if time_diff <= tolerance_seconds:
                return schedule
        
        return None


def deactivate_user_schedules(user_id: int, active_only: bool = True, session=None) -> int:
    """Deactivate a user's schedules. Returns number deactivated."""
    with get_session(session) as s:
        query = s.query(Schedule).filter_by(user_id=user_id)
        if active_only:
            query = query.filter_by(is_active=True)
        schedules = query.all()
        if not schedules:
            return 0
        for schedule in schedules:
            schedule.is_active = False
            s.add(schedule)
        s.commit()
        return len(schedules)


def deactivate_user_schedules_by_type(
    user_id: int, 
    schedule_type: str, 
    active_only: bool = True, 
    session=None
) -> int:
    """Deactivate a user's schedules filtered by type. Returns number deactivated.
    
    Args:
        user_id: The user ID
        schedule_type: Type filter - 'one_time' or 'daily'
        active_only: If True, only deactivate active schedules
        session: Optional DB session
    
    Returns:
        Number of schedules deactivated
    """
    from .domain import is_one_time_schedule_type, is_daily_schedule_type
    
    with get_session(session) as s:
        query = s.query(Schedule).filter_by(user_id=user_id)
        if active_only:
            query = query.filter_by(is_active=True)
        
        # Filter by schedule type
        if schedule_type == "one_time":
            all_schedules = query.all()
            schedules = [sched for sched in all_schedules if is_one_time_schedule_type(sched.schedule_type)]
        elif schedule_type == "daily":
            all_schedules = query.all()
            schedules = [sched for sched in all_schedules if is_daily_schedule_type(sched.schedule_type)]
        else:
            schedules = []
        
        if not schedules:
            return 0
        
        for schedule in schedules:
            schedule.is_active = False
            s.add(schedule)
        s.commit()
        return len(schedules)


def delete_user_schedules(user_id: int, session=None) -> list[int]:
    """Delete all schedules for a user and return list of deleted schedule_ids."""
    with get_session(session) as s:
        schedules = s.query(Schedule).filter_by(user_id=user_id).all()
        if not schedules:
            return []
        ids = [sched.schedule_id for sched in schedules]
        # Bulk delete; use synchronize_session=False for performance
        s.query(Schedule).filter_by(user_id=user_id).delete(synchronize_session=False)
        s.commit()
        return ids
