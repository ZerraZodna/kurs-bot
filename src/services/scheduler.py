"""Scheduler service shim (implementation moved to package)."""

from pathlib import Path

__path__ = [str(Path(__file__).with_name("scheduler"))]

from src.services.scheduler.core import SchedulerService

__all__ = ["SchedulerService"]

