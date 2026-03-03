from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from src.models.database import SessionLocal, JobState, init_db
from src.core.timezone import to_utc


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_state(key: str) -> Optional[str]:
    init_db()
    db = SessionLocal()
    try:
        row = db.query(JobState).filter_by(key=key).first()
        return row.value if row else None
    finally:
        db.close()


def set_state(key: str, value: Optional[str]) -> None:
    init_db()
    db = SessionLocal()
    try:
        row = db.query(JobState).filter_by(key=key).first()
        if row:
            row.value = value
            row.updated_at = _utc_now()
        else:
            row = JobState(key=key, value=value, created_at=_utc_now(), updated_at=_utc_now())
            db.add(row)
        db.commit()
    finally:
        db.close()


def get_state_json(key: str, default: Optional[Any] = None) -> Any:
    raw = get_state(key)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def set_state_json(key: str, value: Any) -> None:
    set_state(key, json.dumps(value))


def get_state_datetime(key: str) -> Optional[datetime]:
    raw = get_state(key)
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        return to_utc(dt)
    except Exception:
        return None


def set_state_datetime(key: str, value: Optional[datetime]) -> None:
    if value is None:
        set_state(key, None)
    else:
        set_state(key, value.isoformat())
