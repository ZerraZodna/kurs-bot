"""Triggers package - trigger definitions and dispatching logic.

Public API:
- `TriggerDispatcher` / `get_trigger_dispatcher`
"""

from .trigger_dispatcher import TriggerDispatcher, get_trigger_dispatcher

__all__ = ["TriggerDispatcher", "get_trigger_dispatcher"]
