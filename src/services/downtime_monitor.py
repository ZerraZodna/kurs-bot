from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from src.config import settings
from src.services.job_state import get_state_datetime, set_state_datetime
from src.services.traffic_tracker import get_last_message_at, is_today_lowest_traffic
from src.services.maintenance import perform_maintenance
from src.scheduler import SchedulerService
from src.services.admin_notifier import send_admin_notification

logger = logging.getLogger(__name__)

_HEARTBEAT_KEY = "last_heartbeat_at"
_DOWNTIME_NOTIFIED_KEY = "last_downtime_notified_at"
_GDPR_RUN_KEY = "last_gdpr_run_at"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_idle(min_minutes: int = 20) -> bool:
    last_msg = get_last_message_at()
    if not last_msg:
        return True
    return (_utc_now() - last_msg) >= timedelta(minutes=min_minutes)


def _gdpr_due() -> bool:
    last_run = get_state_datetime(_GDPR_RUN_KEY)
    if not last_run:
        return True
    return (_utc_now() - last_run) >= timedelta(hours=24)


def _should_force_run() -> bool:
    return is_today_lowest_traffic()


def run_downtime_monitor(poll_seconds: int = 60) -> None:
    """Monitor downtime, recover missed schedules, and run GDPR cleanup when due."""
    while True:
        try:
            now = _utc_now()

            # Downtime detection (offline -> online)
            last_heartbeat = get_state_datetime(_HEARTBEAT_KEY)
            if last_heartbeat:
                grace = timedelta(minutes=settings.DOWNTIME_GRACE_MINUTES)
                if now - last_heartbeat > grace:
                    last_notified = get_state_datetime(_DOWNTIME_NOTIFIED_KEY)
                    if not last_notified or last_notified < last_heartbeat:
                        send_admin_notification("[WARN] Server was offline and is now online (downtime detected).")
                        set_state_datetime(_DOWNTIME_NOTIFIED_KEY, now)

            set_state_datetime(_HEARTBEAT_KEY, now)

            # Recovery check for missed schedules
            missed = SchedulerService.run_recovery_check()
            if missed:
                logger.info("Recovered %s missed schedule(s)", missed)

            # GDPR daily job
            if _gdpr_due():
                if _is_idle(min_minutes=20) or _should_force_run():
                    perform_maintenance(days_keep=settings.MEMORY_ARCHIVE_RETENTION_DAYS)
                    set_state_datetime(_GDPR_RUN_KEY, _utc_now())
                    send_admin_notification(
                        f"[INFO] GDPR cleanup completed at {_utc_now().strftime('%Y-%m-%d %H:%M')}"
                    )

        except Exception as e:
            logger.error("Downtime monitor error: %s", e)

        time.sleep(poll_seconds)
