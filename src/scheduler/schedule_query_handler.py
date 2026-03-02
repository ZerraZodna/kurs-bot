"""Schedule query detection and response helpers.
"""

from __future__ import annotations

from typing import Iterable

from src.models.database import Schedule
from src.services.timezone_utils import format_dt_in_timezone
from src.config import settings
from .domain import is_one_time_schedule_type


async def detect_schedule_status_request(text: str) -> bool:
    """Detect whether `text` is a schedule-status query using simple keyword matching.
    
    Returns True when the message contains schedule query keywords.
    """
    import re
    message = (text or "").strip().lower()
    if not message:
        return False

    # Simple keyword-based detection for schedule status queries
    query_patterns = [
        r"\bwhen\b.*\b(reminder|schedule|lesson)\b",
        r"\bwhat\b.*\btime\b.*\b(reminder|schedule|lesson)\b",
        r"\bshow\b.*\b(reminder|schedule)\b",
        r"\bcheck\b.*\b(reminder|schedule)\b",
        r"\b(reminder|schedule)\b.*\bstatus\b",
        r"\b(reminder|schedule)\b.*\btime\b",
        r"\bmy\b.*\b(reminder|schedule)s?\b",
        r"\blist\b.*\b(reminder|schedule)s?\b",
    ]
    
    # Check if message matches any query pattern
    is_query = any(re.search(p, message) for p in query_patterns)
    
    # Exclude update/create patterns to avoid treating them as queries
    update_patterns = [
        r"\b(set|change|update|modify|create|add|new)\b.*\b(reminder|schedule|time)\b",
        r"\b(reminder|schedule)\b.*\b(set|change|update|modify|create|add)\b",
    ]
    is_update = any(re.search(p, message) for p in update_patterns)
    
    return is_query and not is_update


def build_schedule_status_response(schedules: Iterable[Schedule], tz_name: str = "UTC") -> str:
    schedules = list(schedules)
    if not schedules:
        return "You don't have any active reminders."

    lines = ["Here are your active reminders:"]
    for schedule in schedules:
        if is_one_time_schedule_type(schedule.schedule_type):
            if schedule.next_send_time:
                ts, _ = format_dt_in_timezone(schedule.next_send_time, tz_name)
                lines.append(f"- One-time reminder at {ts:%Y-%m-%d %H:%M}")
            else:
                lines.append("- One-time reminder (time not set)")
            continue

        if schedule.next_send_time:
            ts, _ = format_dt_in_timezone(schedule.next_send_time, tz_name)
            lines.append(f"- Daily reminder at {ts:%H:%M}")
        else:
            lines.append("- Daily reminder (time not set)")

    return "\n".join(lines)
