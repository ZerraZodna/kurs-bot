"""Schedule and reminder setup utilities."""

from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


def check_existing_schedule(db: Session, user_id: int) -> Optional[tuple]:
    """
    Check if user already has an active schedule.
    
    Returns:
        (hour, minute) tuple if schedule exists, None otherwise
    """
    from src.models.database import Schedule

    existing = db.query(Schedule).filter_by(user_id=user_id, is_active=True).first()
    if existing and existing.next_send_time:
        return (existing.next_send_time.hour, existing.next_send_time.minute)
    return None


def create_auto_schedule(db: Session, user_id: int) -> bool:
    """
    Auto-create daily schedule at 07:30 AM for onboarding completion.
    
    Returns:
        True if schedule created, False if already exists or error
    """
    from src.models.database import Schedule
    from src.services.scheduler import SchedulerService

    try:
        existing = db.query(Schedule).filter_by(
            user_id=user_id, is_active=True
        ).first()
        if existing:
            logger.info(f"Schedule already exists for user {user_id}")
            return False

        SchedulerService.create_daily_schedule(
            user_id=user_id,
            lesson_id=None,
            time_str="07:30",
            schedule_type="daily",
            session=db,
        )
        logger.info(f"✓ Auto-created daily schedule at 07:30 AM for user {user_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to auto-create schedule for user {user_id}: {e}")
        return False
