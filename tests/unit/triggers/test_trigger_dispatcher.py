"""
Unit tests for TriggerDispatcher.

Migrated from tests/test_trigger_dispatcher.py to use new test fixtures.
"""

import pytest
from src.triggers.trigger_dispatcher import TriggerDispatcher
from src.models.database import Schedule


class TestTriggerDispatcher:
    """Test suite for TriggerDispatcher."""

    def test_create_schedule_idempotent(self, db_session):
        """Given: An existing schedule with a cron expression for user 42
        When: Dispatching a create_schedule trigger with the same specification
        Then: Should return ok=True with note='already_exists' (idempotent)."""
        # Given: create existing schedule for user 42 with cron expression
        s = Schedule(user_id=42, lesson_id=None, schedule_type="daily", cron_expression="0 9 * * *", is_active=True)
        db_session.add(s)
        db_session.commit()

        dispatcher = TriggerDispatcher(db=db_session)
        match = {"trigger_id": 1, "name": "create_schedule", "action_type": "create_schedule", "score": 0.9, "threshold": 0.5}
        ctx = {"user_id": 42, "schedule_spec": {"cron_expression": "0 9 * * *", "schedule_type": "daily", "time_str": "09:00"}}
        res = dispatcher.dispatch(match, ctx)
        assert res.get("ok") is True
        assert res.get("note") == "already_exists"

