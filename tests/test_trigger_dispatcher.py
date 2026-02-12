import pytest
from src.triggers.trigger_dispatcher import TriggerDispatcher
from src.models.database import SessionLocal, Schedule


@pytest.fixture()
def db():
    db = SessionLocal()
    yield db
    db.close()


def test_create_schedule_idempotent(db):
    # create existing schedule for user 42 with cron expression
    s = Schedule(user_id=42, lesson_id=None, schedule_type="daily", cron_expression="0 9 * * *", is_active=True)
    db.add(s); db.commit()

    dispatcher = TriggerDispatcher(db=db)
    match = {"trigger_id": 1, "name": "create_schedule", "action_type": "create_schedule", "score": 0.9, "threshold": 0.5}
    ctx = {"user_id": 42, "schedule_spec": {"cron_expression": "0 9 * * *", "schedule_type": "daily", "time_str": "09:00"}}
    res = dispatcher.dispatch(match, ctx)
    assert res.get("ok") is True
    assert res.get("note") == "already_exists"
