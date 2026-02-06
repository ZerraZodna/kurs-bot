"""APScheduler helpers that manage scheduler lifecycle and jobs.

This module provides a small facade around the existing scheduler code
so job-management logic can be tested and moved independently of the
`core` module in later steps.
"""
import logging
from typing import Any
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger


logger = logging.getLogger(__name__)


def init_scheduler(app: Any = None):
    """Initialize and return the global scheduler (delegates to core)."""
    from .core import SchedulerService
    return SchedulerService.init_scheduler()


def shutdown_scheduler():
    """Shut down the global scheduler (delegates to core)."""
    from .core import SchedulerService
    return SchedulerService.shutdown()


def _job_id_for(schedule_id: int) -> str:
    return f"schedule_{schedule_id}"


def job_id_for_schedule(schedule_id: int) -> str:
    """Public helper: return job id string for a schedule id."""
    return _job_id_for(schedule_id)


def sync_job_for_schedule(schedule: Any) -> None:
    """Add or replace an APScheduler job to match the provided schedule.

    `schedule` may be an ORM object or a simple object with attributes:
    `schedule_id`, `schedule_type`, `cron_expression`, `next_send_time`.
    """
    from .core import SchedulerService
    scheduler = SchedulerService.get_scheduler()
    job_id = _job_id_for(getattr(schedule, "schedule_id"))

    try:
        if getattr(schedule, "schedule_type", "").startswith("one_time"):
            run_at = getattr(schedule, "next_send_time")
            if run_at is None:
                logger.warning("one_time schedule %s has no next_send_time", job_id)
                return
            trigger = DateTrigger(run_date=run_at, timezone="UTC")
        else:
            cron = getattr(schedule, "cron_expression", None)
            if not cron:
                logger.warning("schedule %s has no cron_expression", job_id)
                return
            trigger = CronTrigger.from_crontab(cron, timezone="UTC")

        scheduler.add_job(
            func=SchedulerService.execute_scheduled_task,
            trigger=trigger,
            args=[getattr(schedule, "schedule_id")],
            id=job_id,
            replace_existing=True,
        )
        logger.info("Synced job %s", job_id)
    except Exception as e:
        logger.warning("Could not sync job %s: %s", job_id, e)


def remove_job_for_schedule(schedule_id: int) -> None:
    from .core import SchedulerService
    scheduler = SchedulerService.get_scheduler()
    job_id = _job_id_for(schedule_id)
    try:
        scheduler.remove_job(job_id)
        logger.info("Removed job %s", job_id)
    except Exception as e:
        logger.warning("Could not remove job %s: %s", job_id, e)
