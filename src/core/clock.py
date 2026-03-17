"""Minimal UTC clock — zero project imports.

This module exists to break circular imports. Models and timezone.py
both need utc_now(), but timezone.py imports from models. So we put
the bare minimum here where nothing else is imported.

ALL code that needs the current UTC time should use utc_now() from
either this module or src.core.timezone (which re-exports it).
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware).

    This is the ONE canonical way to get "now" in this project.
    Never use datetime.now(), datetime.utcnow(), or
    datetime.now(timezone.utc) directly.
    """
    return datetime.now(timezone.utc)
