"""Time parsing helpers for scheduler."""

import logging

logger = logging.getLogger(__name__)


def parse_time_string(time_str: str) -> tuple[int, int]:
    """
    Parse time string to (hour, minute).

    Args:
        time_str: Time like "9:00 AM", "14:30", "morning", "evening"

    Returns:
        Tuple of (hour, minute) in 24-hour format
    """
    time_str = time_str.lower().strip()

    # Handle named times
    named_times = {
        "morning": (9, 0),
        "afternoon": (14, 0),
        "evening": (19, 0),
        "night": (21, 0),
        "morgenen": (9, 0),  # Norwegian
        "ettermiddagen": (14, 0),
        "kvelden": (19, 0),
    }

    if time_str in named_times:
        return named_times[time_str]

    # Parse "9:00 AM" or "14:30" format
    try:
        # Remove spaces
        time_str = time_str.replace(" ", "")

        # Handle AM/PM
        is_pm = "pm" in time_str
        is_am = "am" in time_str
        time_str = time_str.replace("am", "").replace("pm", "")

        # Split by colon
        if ":" in time_str:
            hour_str, minute_str = time_str.split(":")
            hour = int(hour_str)
            minute = int(minute_str)
        else:
            hour = int(time_str)
            minute = 0

        # Convert to 24-hour if PM
        if is_pm and hour < 12:
            hour += 12
        elif is_am and hour == 12:
            hour = 0

        # Validate
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return (hour, minute)

    except (ValueError, IndexError):
        pass

    # Default to 9 AM if parsing fails
    logger.warning(f"Could not parse time '{time_str}', defaulting to 9:00 AM")
    return (9, 0)


def compute_next_send_and_cron(time_str: str, tz_name: str = "UTC", now_utc=None):
    """Compute next send time (UTC) and cron expression for a given local time string.

    Args:
        time_str: user-local time like "9:00", "10:15 AM", or named times
        tz_name: IANA timezone name for the user (defaults to UTC)
        now_utc: optional reference `datetime` in UTC; defaults to current UTC time

    Returns:
        (next_send_utc: datetime, cron_expression: str)
    """
    from datetime import datetime, timezone, timedelta
    try:
        from zoneinfo import ZoneInfo
    except Exception:
        ZoneInfo = None

    hour, minute = parse_time_string(time_str)

    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    # Resolve timezone
    try:
        tzinfo = ZoneInfo(tz_name) if ZoneInfo else timezone.utc
    except Exception:
        tzinfo = timezone.utc

    # Compute local next occurrence then convert to UTC
    local_now = now_utc.astimezone(tzinfo)
    local_next = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if local_next <= local_now:
        local_next += timedelta(days=1)

    next_send = local_next.astimezone(timezone.utc)
    cron_expression = f"{next_send.minute} {next_send.hour} * * *"
    return next_send, cron_expression
