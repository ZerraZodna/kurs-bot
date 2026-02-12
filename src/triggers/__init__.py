"""Triggers package - trigger definitions and matching logic.

Public API:
- `TriggerMatcher` / `get_trigger_matcher`
- `TriggerDispatcher` / `get_trigger_dispatcher`
"""

from .trigger_matcher import TriggerMatcher, get_trigger_matcher
from .trigger_dispatcher import TriggerDispatcher, get_trigger_dispatcher

__all__ = ["TriggerMatcher", "get_trigger_matcher", "TriggerDispatcher", "get_trigger_dispatcher"]
