from __future__ import annotations

import logging
from src.core.timezone import datetime
from typing import Dict, List, Optional

from src.core.timezone import utc_now
from src.scheduler.job_state import get_state_json, set_state_datetime, set_state_json

logger = logging.getLogger(__name__)

_BUCKET_KEY = "traffic_buckets"
_LAST_MESSAGE_KEY = "last_message_at"
_MAX_BUCKETS = 21  # 3-week rolling buffer


def _today_str() -> str:
    return utc_now().date().isoformat()


def _load_buckets() -> List[Dict[str, int]]:
    buckets = get_state_json(_BUCKET_KEY, default=[])
    if isinstance(buckets, list):
        return buckets
    return []


def _save_buckets(buckets: List[Dict[str, int]]) -> None:
    set_state_json(_BUCKET_KEY, buckets[-_MAX_BUCKETS:])


def record_traffic_event() -> None:
    """Increment today's traffic bucket and update last message time."""
    today = _today_str()
    buckets = _load_buckets()
    if buckets and buckets[-1].get("date") == today:
        buckets[-1]["count"] = int(buckets[-1].get("count", 0)) + 1
    else:
        buckets.append({"date": today, "count": 1})
    _save_buckets(buckets)
    set_state_datetime(_LAST_MESSAGE_KEY, utc_now())


def get_last_message_at() -> Optional[datetime]:
    from src.scheduler.job_state import get_state_datetime

    return get_state_datetime(_LAST_MESSAGE_KEY)


def is_today_lowest_traffic() -> bool:
    """Return True if today's count is <= min of prior same weekday buckets."""
    today = utc_now().date()
    today_str = today.isoformat()
    buckets = _load_buckets()
    today_count = 0
    if buckets and buckets[-1].get("date") == today_str:
        today_count = int(buckets[-1].get("count", 0))

    weekday = today.weekday()
    history = []
    for bucket in buckets:
        date_str = bucket.get("date")
        if not date_str or date_str == today_str:
            continue
        try:
            b_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            continue
        if b_date.weekday() == weekday:
            history.append(int(bucket.get("count", 0)))

    if not history:
        return True

    return today_count <= min(history)
