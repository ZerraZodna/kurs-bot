from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from src.core.timezone import utc_now
from src.models.database import JobState, Schedule, SessionLocal, get_session

logger = logging.getLogger(__name__)


def purge_inactive_schedules(days_keep: int = 7, session: Session | None = None) -> int:
    """Delete schedules that are inactive and older than days_keep. Returns number deleted."""
    with get_session(session) as s:
        cutoff = utc_now() - timedelta(days=days_keep)
        q = s.query(Schedule).filter(
            not Schedule.is_active,
            Schedule.created_at < cutoff,
        )
        deleted = q.count()
        q.delete(synchronize_session=False)
        s.commit()
        logger.info("Purged %s inactive Schedule rows older than %s days", deleted, days_keep)
        return deleted


def purge_job_states(days_keep: int = 30, session: Session | None = None) -> int:
    """Delete JobState rows older than days_keep. Returns number deleted.

    Note: `JobState` is a simple key/value table; ensure callers are ok with
    removing old keys before enabling this in production.
    """
    with get_session(session) as s:
        cutoff = utc_now() - timedelta(days=days_keep)
        q = s.query(JobState).filter(JobState.created_at < cutoff)
        deleted = q.count()
        q.delete(synchronize_session=False)
        s.commit()
        logger.info("Purged %s JobState rows older than %s days", deleted, days_keep)
        return deleted
