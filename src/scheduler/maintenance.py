from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from src.models.database import SessionLocal, Schedule, JobState

logger = logging.getLogger(__name__)


def purge_inactive_schedules(days_keep: int = 7, session: Optional[Session] = None) -> int:
    """Delete schedules that are inactive and older than days_keep. Returns number deleted."""
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_keep)
        q = session.query(Schedule).filter(
            Schedule.is_active == False,
            Schedule.created_at < cutoff,
        )
        deleted = q.count()
        q.delete(synchronize_session=False)
        session.commit()
        logger.info("Purged %s inactive Schedule rows older than %s days", deleted, days_keep)
        return deleted
    finally:
        if close_session:
            session.close()


def purge_job_states(days_keep: int = 30, session: Optional[Session] = None) -> int:
    """Delete JobState rows older than days_keep. Returns number deleted.

    Note: `JobState` is a simple key/value table; ensure callers are ok with
    removing old keys before enabling this in production.
    """
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_keep)
        q = session.query(JobState).filter(JobState.created_at < cutoff)
        deleted = q.count()
        q.delete(synchronize_session=False)
        session.commit()
        logger.info("Purged %s JobState rows older than %s days", deleted, days_keep)
        return deleted
    finally:
        if close_session:
            session.close()
