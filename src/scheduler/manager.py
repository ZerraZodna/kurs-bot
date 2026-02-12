"""Pure DB helpers for Schedule records.

This module contains functions that perform CRUD operations on the
`Schedule` model without interacting with APScheduler. It is intended to
be a thin, testable layer so the APScheduler wiring can live separately.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from src.models.database import SessionLocal, Schedule
from src.services.timezone_utils import to_utc


def create_schedule(
    user_id: int,
    lesson_id: Optional[int],
    schedule_type: str,
    cron_expression: str,
    next_send_time: Optional[datetime] = None,
    session=None,
) -> Schedule:
    close = False
    if session is None:
        session = SessionLocal()
        close = True

    try:
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
    finally:
        if close:
            session.close()


def update_schedule(schedule_id: int, updates: Dict[str, Any], session=None) -> Optional[Schedule]:
    """Apply safe updates to a schedule and return the updated object.

    Supported update keys: `cron_expression`, `next_send_time`, `is_active`, `lesson_id`.
    """
    close = False
    if session is None:
        session = SessionLocal()
        close = True

    try:
        sched = session.query(Schedule).filter_by(schedule_id=schedule_id).first()
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
            session.add(sched)
            session.commit()
            session.refresh(sched)

        return sched
    finally:
        if close:
            session.close()


def deactivate_schedule(schedule_id: int, session=None) -> bool:
    """Mark a schedule inactive. Returns True if changed, False if not found/already inactive."""
    close = False
    if session is None:
        session = SessionLocal()
        close = True

    try:
        sched = session.query(Schedule).filter_by(schedule_id=schedule_id).first()
        if not sched or not sched.is_active:
            return False
        sched.is_active = False
        session.add(sched)
        session.commit()
        return True
    finally:
        if close:
            session.close()


def get_user_schedules(user_id: int, active_only: bool = True, session=None) -> List[Schedule]:
    close = False
    if session is None:
        session = SessionLocal()
        close = True

    try:
        query = session.query(Schedule).filter_by(user_id=user_id)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(Schedule.created_at).all()
    finally:
        if close:
            session.close()


def find_active_daily_schedule(user_id: int, session=None) -> Optional[Schedule]:
    close = False
    if session is None:
        session = SessionLocal()
        close = True
    try:
        return (
            session.query(Schedule)
            .filter_by(user_id=user_id, is_active=True, schedule_type="daily")
            .order_by(Schedule.created_at)
            .first()
        )
    finally:
        if close:
            session.close()


def deactivate_user_schedules(user_id: int, active_only: bool = True, session=None) -> int:
    """Deactivate a user's schedules. Returns number deactivated."""
    close = False
    if session is None:
        session = SessionLocal()
        close = True
    try:
        query = session.query(Schedule).filter_by(user_id=user_id)
        if active_only:
            query = query.filter_by(is_active=True)
        schedules = query.all()
        if not schedules:
            return 0
        for s in schedules:
            s.is_active = False
            session.add(s)
        session.commit()
        return len(schedules)
    finally:
        if close:
            session.close()


def delete_user_schedules(user_id: int, session=None) -> list[int]:
    """Delete all schedules for a user and return list of deleted schedule_ids."""
    close = False
    if session is None:
        session = SessionLocal()
        close = True

    try:
        schedules = session.query(Schedule).filter_by(user_id=user_id).all()
        if not schedules:
            return []
        ids = [s.schedule_id for s in schedules]
        # Bulk delete; use synchronize_session=False for performance
        session.query(Schedule).filter_by(user_id=user_id).delete(synchronize_session=False)
        session.commit()
        return ids
    finally:
        if close:
            session.close()
