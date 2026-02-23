"""Compatibility wrappers for scheduler job-state helpers.

Canonical implementation lives in `src.scheduler.job_state`.
"""

from src.scheduler.job_state import (
    get_state,
    set_state,
    get_state_json,
    set_state_json,
    get_state_datetime,
    set_state_datetime,
)

__all__ = [
    "get_state",
    "set_state",
    "get_state_json",
    "set_state_json",
    "get_state_datetime",
    "set_state_datetime",
]
