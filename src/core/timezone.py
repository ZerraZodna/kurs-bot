"""Timezone utilities for user-aware scheduling.

This module centralizes timezone helpers for reuse across packages.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo


def _normalize_tz_name(tz_name: Optional[str]) -> Optional[str]:
    if not tz_name:
        return None
    normalized = tz_name.strip()
    if normalized in {"CET", "CEST"}:
        return "Europe/Oslo"
    if normalized in {"UTC", "GMT"}:
        return "UTC"
    return normalized


def _get_local_timezone_name() -> str:
    try:
        tzinfo = datetime.now().astimezone().tzinfo
        if tzinfo is None:
            return "UTC"
        if isinstance(tzinfo, ZoneInfo):
            return tzinfo.key
        tzname = _normalize_tz_name(tzinfo.tzname(None))
        return tzname or "UTC"
    except Exception:
        return "UTC"


def infer_timezone_from_language(language: Optional[str]) -> str:
    if not language:
        return _get_local_timezone_name()
    lang = language.strip().lower()
    if lang in {"norwegian", "norsk", "nb", "no", "bokmal", "bokmål"}:
        return "Europe/Oslo"
    if "norwegian" in lang:
        return "Europe/Oslo"
    return _get_local_timezone_name()


def get_user_timezone_from_db(session, user_id: int, default: str = "Europe/Oslo") -> str:
    """Get user's timezone from DB, inferring from language if needed.

    Order of resolution:
    1. User.timezone if explicitly set
    2. Inferred from User.language if available
    3. Default (UTC)
    """
    from src.models.database import User  # Import here to avoid circular imports

    try:
        user = session.query(User).filter_by(user_id=user_id).first()
        if user:
            # First check if timezone is explicitly set
            tz = getattr(user, "timezone", None)
            if tz:
                return str(tz)
            # Otherwise infer from language
            language = getattr(user, "language", None)
            if language:
                return infer_timezone_from_language(language)
    except Exception:
        pass
    return default


def format_dt_in_timezone(dt: datetime, tz_name: Optional[str]) -> Tuple[datetime, str]:
    resolved_name = tz_name or "UTC"
    try:
        tzinfo = ZoneInfo(resolved_name)
    except Exception:
        tzinfo = timezone.utc
        resolved_name = "UTC"

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(tzinfo), resolved_name


def to_utc(dt: datetime, tz_name: Optional[str] = None) -> datetime:
    """Return an aware UTC datetime.

    - If ``dt`` has tzinfo, convert it to UTC.
    - If ``dt`` is naive and ``tz_name`` is provided, interpret it as local
      time in that timezone and convert to UTC.
    - If ``dt`` is naive and no ``tz_name`` provided, assume UTC.
    """
    if dt is None:
        raise ValueError("dt must be a datetime")

    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)

    # naive
    if tz_name:
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = timezone.utc
        local = dt.replace(tzinfo=tz)
        return local.astimezone(timezone.utc)

    # assume UTC
    return dt.replace(tzinfo=timezone.utc)


def from_utc(dt: datetime, tz_name: Optional[str]) -> datetime:
    """Convert an aware UTC datetime to the given timezone.

    If dt is naive it is assumed to be UTC.
    """
    if dt is None:
        raise ValueError("dt must be a datetime")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    resolved_name = tz_name or "UTC"
    try:
        tz = ZoneInfo(resolved_name)
    except Exception:
        tz = timezone.utc

    return dt.astimezone(tz)


def parse_local_time_to_utc(time_str: str, tz_name: str, now_utc: Optional[datetime] = None) -> datetime:
    """Parse a user-local time string and return the next occurrence in UTC.

    Uses the scheduler's simple parser to interpret strings like "9:00", "10:15 AM",
    or named times (morning/evening). The returned datetime is timezone-aware UTC.
    """
    from datetime import timedelta

    # import parser from scheduler to reuse parsing rules
    try:
        from src.scheduler.time_utils import parse_time_string
    except Exception:
        # fallback simple parser
        def parse_time_string(ts: str):
            parts = ts.split(":")
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
            return int(ts), 0

    hour, minute = parse_time_string(time_str)

    if now_utc is None:
        from datetime import datetime as _dt

        now_utc = _dt.now(timezone.utc)

    try:
        tz = ZoneInfo(tz_name or "UTC")
    except Exception:
        tz = timezone.utc

    local_now = now_utc.astimezone(tz)
    local_next = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if local_next <= local_now:
        local_next = local_next + timedelta(days=1)

    return local_next.astimezone(timezone.utc)


def validate_timezone_name(tz_name: Optional[str]) -> bool:
    """Return True if tz_name is a valid IANA timezone (or UTC), False otherwise."""
    if not tz_name:
        return False
    try:
        # Try resolving with ZoneInfo; if it fails an exception will be raised
        ZoneInfo(str(tz_name))
        return True
    except Exception:
        return False


def resolve_timezone_name(tz_name: Optional[str]) -> Optional[str]:
    """Try to resolve a user-provided timezone to a canonical IANA name.

    Strategy:
    - If tz_name is already a valid IANA name, return it.
    - Try some normalization (replace dots/spaces with underscores) and retry.
    - Check a small mapping for common Windows timezone names -> IANA.
    - Return None if no resolution found.
    """
    if not tz_name:
        return None

    candidate = tz_name.strip()
    # Try as-is
    try:
        ZoneInfo(candidate)
        return candidate
    except Exception:
        pass

    # Normalize common punctuation/spacing
    cand2 = candidate.replace(" ", "_").replace(".", "")
    try:
        ZoneInfo(cand2)
        return cand2
    except Exception:
        pass

    # Small mapping for common non-IANA names (including Windows tz names observed in the wild)
    mapping = {
        "w. europe standard time": "Europe/Berlin",
        "w europe standard time": "Europe/Berlin",
        "w europe": "Europe/Berlin",
        "central europe standard time": "Europe/Berlin",
        "romance standard time": "Europe/Paris",
        "gmt standard time": "Europe/London",
        "pacific standard time": "America/Los_Angeles",
        "eastern standard time": "America/New_York",
    }

    key = candidate.strip().lower()
    if key in mapping:
        return mapping[key]

    # Not resolved
    return None


# Re-export from clock.py (which has zero project imports) to avoid circular imports.
from src.core.clock import utc_now  # noqa: F401 — re-export


def utc_date_now() -> date:
    """Return current UTC date (naive). Central point for date comparisons."""
    return utc_now().date()


def utc_date(dt: datetime) -> date:
    """Convert datetime to UTC date."""
    if dt is None:
        return utc_date_now()
    return to_utc(dt).date()


def date_is_past(dt: datetime) -> bool:
    """Check if given datetime's date is before today (UTC). Central date comparison."""
    return utc_date(dt) < utc_date_now()


def utc_now_plus(minutes: int = 0, hours: int = 0, days: int = 0) -> datetime:
    """UTC now + timedelta. Central timedelta helper."""
    from datetime import timedelta

    td = timedelta(minutes=minutes, hours=hours, days=days)
    return utc_now() + td


def format_datetime_for_display(iso_string: Optional[str]) -> str:
    """Format an ISO8601 datetime string for user display.

    Converts '2026-03-02T15:14:00' to '2026-03-02 15:14' format.
    Handles timezone suffixes and returns a user-friendly string.

    Args:
        iso_string: ISO8601 datetime string (e.g., '2026-03-02T15:14:00' or '2026-03-02T15:14:00+00:00')

    Returns:
        Formatted string for display (e.g., '2026-03-02 15:14'), or original string if parsing fails
    """
    if not iso_string:
        return "unknown"

    try:
        # Parse the ISO string
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        # Format as YYYY-MM-DD HH:MM (without seconds, with space instead of T)
        return f"{dt:%Y-%m-%d %H:%M}"
    except Exception:
        # If parsing fails, just replace T with space as fallback
        if "T" in iso_string:
            return iso_string.replace("T", " ")[:16]  # Take up to minutes
        return iso_string
