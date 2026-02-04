"""Schedule query detection and response helpers."""

from __future__ import annotations

from datetime import timezone
from typing import Iterable

from src.models.database import Schedule


def detect_schedule_status_request(text: str) -> bool:
    message = (text or "").strip().lower()
    if not message:
        return False

    question_terms = (
        "what",
        "which",
        "when",
        "do i have",
        "my",
        "mine",
        "hvilken",
        "hvilke",
        "når",
        "har jeg",
        "mine",
    )

    schedule_terms = (
        "reminder",
        "reminders",
        "schedule",
        "schedules",
        "daily",
        "lesson",
        "lessons",
        "påminn",
        "påminnelser",
        "plan",
        "leksjon",
        "leksjoner",
        "daglig",
    )

    return any(q in message for q in question_terms) and any(s in message for s in schedule_terms)


def build_schedule_status_response(schedules: Iterable[Schedule]) -> str:
    schedules = list(schedules)
    if not schedules:
        return "You don't have any active reminders."

    lines = ["Here are your active reminders:"]
    for schedule in schedules:
        if schedule.schedule_type.startswith("one_time"):
            if schedule.next_send_time:
                ts = schedule.next_send_time.astimezone(timezone.utc)
                lines.append(f"- One-time reminder at {ts:%Y-%m-%d %H:%M} UTC")
            else:
                lines.append("- One-time reminder (time not set)")
            continue

        if schedule.next_send_time:
            ts = schedule.next_send_time.astimezone(timezone.utc)
            lines.append(f"- Daily reminder at {ts:%H:%M} UTC")
        else:
            lines.append("- Daily reminder (time not set)")

    return "\n".join(lines)
