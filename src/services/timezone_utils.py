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
    try:
        user = memory_manager.db.query(User).filter_by(user_id=user_id).first()
        if user and getattr(user, "timezone", None):
            return str(user.timezone)
    except Exception:
        pass

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
    try:
        user = memory_manager.db.query(User).filter_by(user_id=user_id).first()
        if user:
            user.timezone = tz_name
            memory_manager.db.add(user)
            memory_manager.db.commit()
            return tz_name
    except Exception:
        # ignore DB write errors and fall back to memory storage
        try:
            memory_manager.db.rollback()
        except Exception:
            pass

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
