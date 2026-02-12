"""Schedule query detection and response helpers.
"""

from __future__ import annotations

from typing import Iterable

from src.models.database import Schedule
from src.services.timezone_utils import format_dt_in_timezone
from src.triggers.trigger_matcher import get_trigger_matcher
from src.config import settings


async def detect_schedule_status_request(text: str) -> bool:
    """Detect whether `text` is a schedule-status query by delegating to
    the central TriggerMatcher. Returns True when the top schedule-query
    similarity exceeds the configured threshold and is not exceeded by
    an update/create schedule trigger (avoid treating update requests as
    status queries).
    """
    message = (text or "").strip()
    if not message:
        return False

    # Delegate matching to the central TriggerMatcher

    matcher = get_trigger_matcher()
    matches = await matcher.match_triggers(message, top_k=3)
    if not matches:
        return False

    max_status = max((m["score"] for m in matches if m.get("action_type") == "query_schedule"), default=0.0)
    max_change = max((m["score"] for m in matches if m.get("action_type") in ("update_schedule", "create_schedule")), default=0.0)

    threshold = float(getattr(settings, "TRIGGER_SIMILARITY_THRESHOLD", 0.75))
    return (max_status >= threshold) and (max_status >= max_change)


def build_schedule_status_response(schedules: Iterable[Schedule], tz_name: str = "UTC") -> str:
    schedules = list(schedules)
    if not schedules:
        return "You don't have any active reminders."

    lines = ["Here are your active reminders:"]
    for schedule in schedules:
        if schedule.schedule_type.startswith("one_time"):
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
