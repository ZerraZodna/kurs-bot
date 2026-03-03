"""Schedule and reminder setup utilities."""

from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session
import logging

from src.scheduler import api as scheduler_api
from src.scheduler.domain import SCHEDULE_TYPE_DAILY

logger = logging.getLogger(__name__)


def check_existing_schedule(db: Session, user_id: int) -> Optional[tuple]:
    """
    Check if user already has an active schedule.
    
    Returns:
        (hour, minute) tuple if schedule exists, None otherwise
    """
    sched = scheduler_api.find_active_daily_schedule(user_id, session=db)
    if sched and sched.next_send_time:
        return (sched.next_send_time.hour, sched.next_send_time.minute)
    return None


def create_auto_schedule(db: Session, user_id: int) -> bool:
    """
    Auto-create daily schedule at 07:30 AM for onboarding completion.
    
    Returns:
        True if schedule created, False if already exists or error
    """
    try:
        existing = scheduler_api.find_active_daily_schedule(user_id, session=db)
        if existing:
            logger.info(f"Schedule already exists for user {user_id}")
            return False

        # Pick the user's current lesson (if known) so the first automated
        # delivery does not always default to Lesson 1 for continuing users.
        try:
            from src.memories import MemoryManager
            from src.lessons.state import get_current_lesson

            memory_manager = MemoryManager(db)
            cur = get_current_lesson(memory_manager, user_id)
            # Accept numeric or numeric-string lesson ids
            lesson_id = None
            if cur is not None:
                try:
                    lesson_id = int(str(cur))
                except Exception:
                    lesson_id = None
        except Exception:
            lesson_id = None

        scheduler_api.create_daily_schedule(
            user_id=user_id,
            lesson_id=lesson_id,
            time_str="07:30",
            schedule_type=SCHEDULE_TYPE_DAILY,
            session=db,
        )
        logger.info(f"✓ Auto-created daily schedule at 07:30 AM for user {user_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to auto-create schedule for user {user_id}: {e}")
        return False
