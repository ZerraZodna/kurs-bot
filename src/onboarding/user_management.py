"""User cleanup and management utilities."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from src.memories.user_data_service import delete_user_content_rows

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
        from src.models.database import User
        from src.services.admin_notifier import send_admin_notification

        user = db.query(User).filter_by(user_id=user_id).first()
        name = " ".join([n for n in [getattr(user, "first_name", None), getattr(user, "last_name", None)] if n])
        if not name:
            name = str(user_id)

        # Delete in order of dependencies
        delete_user_content_rows(db, user_id)

        db.query(User).filter_by(user_id=user_id).delete()

        db.commit()
        logger.info(f"✓ Deleted user {user_id} and all associated data")
        send_admin_notification(f"[INFO] User left: {name} (reason: declined).")
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
    from src.core.timezone import to_utc, utc_now
    from src.models.database import User

    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        return False

    now = utc_now()
    time_diff = now - to_utc(user.created_at)
    return time_diff.total_seconds() < (threshold_minutes * 60)
