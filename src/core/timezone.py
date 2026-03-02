"""Timezone utilities moved from `src.services.timezone_utils`.

This module centralizes timezone helpers for reuse across packages.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

from zoneinfo import ZoneInfo

from src.memories import MemoryManager
from src.models.database import User


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


def get_user_timezone_name(
    memory_manager: MemoryManager,
    user_id: int,
    fallback_language: Optional[str] = None,
) -> str:
    # First check DB user column (preferred)
    user = memory_manager.db.query(User).filter_by(user_id=user_id).first()
    if user and getattr(user, "timezone", None):
        return str(user.timezone)

    # Do NOT use memory-stored timezone. Only use DB user timezone (preferred),
    # otherwise infer from language or return UTC.
    if fallback_language:
        return infer_timezone_from_language(fallback_language)
    return "UTC"


def ensure_user_timezone(
    memory_manager: MemoryManager,
    user_id: int,
    language: Optional[str],
    source: str = "onboarding_service",
) -> str:
    tz_name = infer_timezone_from_language(language)
    user = memory_manager.db.query(User).filter_by(user_id=user_id).first()
    if user:
        if getattr(user, "timezone", None):
            return str(user.timezone)
        user.timezone = tz_name
        memory_manager.db.add(user)
        memory_manager.db.commit()
        return tz_name

    return tz_name


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
    if dt is None:
        raise ValueError("dt must be a datetime")

    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)

    if tz_name:
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = timezone.utc
        local = dt.replace(tzinfo=tz)
        return local.astimezone(timezone.utc)

    return dt.replace(tzinfo=timezone.utc)


def from_utc(dt: datetime, tz_name: Optional[str]) -> datetime:
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
    from datetime import timedelta
    try:
        from src.scheduler.time_utils import parse_time_string
    except Exception:
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
    if not tz_name:
        return False
    try:
        ZoneInfo(str(tz_name))
        return True
    except Exception:
        return False


def resolve_timezone_name(tz_name: Optional[str]) -> Optional[str]:
    if not tz_name:
        return None

    candidate = tz_name.strip()
    try:
        ZoneInfo(candidate)
        return candidate
    except Exception:
        pass

    cand2 = candidate.replace(" ", "_").replace(".", "")
    try:
        ZoneInfo(cand2)
        return cand2
    except Exception:
        pass

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

    return None


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
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        # Format as YYYY-MM-DD HH:MM (without seconds, with space instead of T)
        return f"{dt:%Y-%m-%d %H:%M}"
    except Exception:
        # If parsing fails, just replace T with space as fallback
        if 'T' in iso_string:
            return iso_string.replace('T', ' ')[:16]  # Take up to minutes
        return iso_string
