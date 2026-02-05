"""Scheduler service package.

Expose commonly monkeypatched symbols for tests (e.g. `SessionLocal`, `send_message`).
"""

from src.models.database import SessionLocal
from src.integrations.telegram import send_message

from .core import SchedulerService

__all__ = ["SchedulerService", "SessionLocal", "send_message"]
