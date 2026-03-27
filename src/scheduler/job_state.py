from __future__ import annotations

import json
from src.core.timezone import datetime
from typing import Any

from src.core.timezone import to_utc, utc_now
from src.models.database import JobState, SessionLocal, init_db


def get_state(key: str) -> str | None:
    init_db()
    db = SessionLocal()
    try:
        row = db.query(JobState).filter_by(key=key).first()
        return row.value if row else None
    finally:
        db.close()


def set_state(key: str, value: str | None) -> None:
    init_db()
    db = SessionLocal()
    try:
        row = db.query(JobState).filter_by(key=key).first()
        if row:
            row.value = value
            row.updated_at = utc_now()
        else:
            row = JobState(key=key, value=value, created_at=utc_now(), updated_at=utc_now())
            db.add(row)
        db.commit()
    finally:
        db.close()


def get_state_json(key: str, default: Any | None = None) -> Any:
    raw = get_state(key)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def set_state_json(key: str, value: Any) -> None:
    set_state(key, json.dumps(value))


def get_state_datetime(key: str) -> datetime | None:
    raw = get_state(key)
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        return to_utc(dt)
    except Exception:
        return None


def set_state_datetime(key: str, value: datetime | None) -> None:
    if value is None:
        set_state(key, None)
    else:
        set_state(key, value.isoformat())
