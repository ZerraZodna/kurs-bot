"""Top-level scheduler package.

Provides the scheduler façade and exposes SchedulerService and related
utilities (jobs, manager, time utilities, helpers) for use by the
application.
"""

from src.integrations.telegram import send_message
from src.models.database import SessionLocal

from . import jobs, manager, time_utils
from .core import SchedulerService

__all__ = [
    "SchedulerService",
    "SessionLocal",
    "send_message",
    "jobs",
    "manager",
    "time_utils",
]


def delete_user_schedules_and_remove_jobs(user_id: int, session=None) -> list[int]:
    """Delete a user's schedules (DB) and attempt to remove APScheduler jobs.

    Returns list of deleted schedule_ids.
    """
    from . import manager as _manager

    try:
        from . import jobs as _jobs
    except Exception:
        _jobs = None

    deleted = _manager.delete_user_schedules(user_id=user_id, session=session)
    if _jobs and deleted:
        for sid in deleted:
            try:
                _jobs.remove_job_for_schedule(sid)
            except Exception:
                # best-effort; ignore failures
                pass
    return deleted


def deactivate_user_schedules_and_remove_jobs(user_id: int, active_only: bool = True, session=None) -> int:
    """Deactivate a user's schedules in DB and attempt to remove APScheduler jobs.

    Returns number of schedules deactivated.
    """
    from . import manager as _manager

    try:
        from . import jobs as _jobs
    except Exception:
        _jobs = None

    schedules = _manager.get_user_schedules(user_id=user_id, active_only=active_only, session=session)
    if not schedules:
        return 0

    schedule_ids = [s.schedule_id for s in schedules]
    count = _manager.deactivate_user_schedules(user_id=user_id, active_only=active_only, session=session)

    if _jobs and schedule_ids:
        for sid in schedule_ids:
            try:
                _jobs.remove_job_for_schedule(sid)
            except Exception:
                # best-effort; ignore failures
                pass

    return count
