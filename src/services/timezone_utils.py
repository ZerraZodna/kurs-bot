"""Timezone utilities for user-aware scheduling."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple, Any, Dict, List

from zoneinfo import ZoneInfo

from src.services.memory_manager import MemoryManager
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

    # Fallback to memory-stored timezone (older codepath)
    memories: List[Dict[str, Any]] = memory_manager.get_memory(  # type: ignore[reportUnknownMemberType]
        user_id, "user_timezone"
    )
    if memories:
        value = memories[0].get("value")
        if value:
            return str(value)
    if fallback_language:
        return infer_timezone_from_language(fallback_language)
    return "UTC"


def ensure_user_timezone(
    memory_manager: MemoryManager,
    user_id: int,
    language: Optional[str],
    source: str = "onboarding_service",
) -> str:
    existing: List[Dict[str, Any]] = memory_manager.get_memory(  # type: ignore[reportUnknownMemberType]
        user_id, "user_timezone"
    )
    if existing:
        value = existing[0].get("value")
        if value:
            return str(value)

    tz_name = infer_timezone_from_language(language)
    # Persist to DB if possible
    user = memory_manager.db.query(User).filter_by(user_id=user_id).first()
    if user:
        user.timezone = tz_name
        memory_manager.db.add(user)
        memory_manager.db.commit()
        return tz_name

    memory_manager.store_memory(
        user_id=user_id,
        key="user_timezone",
        value=tz_name,
        confidence=0.7,
        source=source,
        category="profile",
    )
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
        from src.services.scheduler.time_utils import parse_time_string
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
