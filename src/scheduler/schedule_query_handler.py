"""Schedule query detection and response helpers.
"""

from __future__ import annotations

from typing import Iterable

from src.models.database import Schedule
from src.core.timezone import format_dt_in_timezone
from .domain import is_one_time_schedule_type


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
