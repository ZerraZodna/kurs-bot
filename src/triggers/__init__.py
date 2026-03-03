"""Triggers package - trigger definitions and dispatching logic.

Public API:
- `handle_triggers` - Process function calls from AI responses
"""

from .triggering import handle_triggers

__all__ = ["handle_triggers"]
