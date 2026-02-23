"""Scheduler lifecycle helpers.

Contains APScheduler initialization/shutdown and singleton access.
"""

from __future__ import annotations

import logging
from datetime import timezone
from typing import Optional

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from src.config import settings

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: Optional[BackgroundScheduler] = None


def init_scheduler() -> BackgroundScheduler:
    """Initialize the APScheduler background scheduler."""
    global _scheduler

    if _scheduler is not None:
        logger.warning("Scheduler already initialized")
        return _scheduler

    # Configure job store (stores jobs in database)
    jobstores = {
        "default": SQLAlchemyJobStore(url=settings.DATABASE_URL, tablename="apscheduler_jobs")
    }

    # Create scheduler
    _scheduler = BackgroundScheduler(
        jobstores=jobstores,
        timezone=timezone.utc,
    )

    _scheduler.start()
    logger.info("✓ Scheduler initialized and started")

    return _scheduler


def shutdown_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=True)
        _scheduler = None
        logger.info("✓ Scheduler shut down")


def get_scheduler() -> BackgroundScheduler:
    """Get the scheduler instance, initializing if needed."""
    global _scheduler
    if _scheduler is None:
        return init_scheduler()
    return _scheduler
