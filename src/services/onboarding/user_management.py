"""User cleanup and management utilities."""

from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


def delete_user_and_data(db: Session, user_id: int) -> bool:
    """
    Delete a user and all associated data from the database.
    Called when user declines consent during onboarding.

    Deletes:
    - All memories associated with user
    - All message logs
    - All schedules
    - The user itself

    Args:
        db: Database session
        user_id: User ID to delete

    Returns:
        True if successful, False otherwise
    """
    try:
        from src.models.database import User, Memory, MessageLog, Schedule

        # Delete in order of dependencies
        db.query(Memory).filter_by(user_id=user_id).delete()
        db.query(MessageLog).filter_by(user_id=user_id).delete()
        db.query(Schedule).filter_by(user_id=user_id).delete()
        db.query(User).filter_by(user_id=user_id).delete()

        db.commit()
        logger.info(f"✓ Deleted user {user_id} and all associated data")
        return True

    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        db.rollback()
        return False


def is_user_new(db: Session, user_id: int, threshold_minutes: int = 10) -> bool:
    """
    Check if user is new (created within threshold).

    Args:
        db: Database session
        user_id: User ID to check
        threshold_minutes: How many minutes to consider "new"

    Returns:
        True if user created within threshold
    """
    from datetime import datetime, timezone
    from src.models.database import User

    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        return False

    now = datetime.now(timezone.utc)
    time_diff = now - user.created_at.replace(tzinfo=timezone.utc)
    return time_diff.total_seconds() < (threshold_minutes * 60)
