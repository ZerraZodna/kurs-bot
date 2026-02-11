import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone

from src.models.database import Base, User, Lesson, Schedule, Memory, MessageLog
from src.services import scheduler as scheduler_module


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    user = User(
        external_id="99999",
        channel="telegram",
        first_name="Sched",
        last_name="Test",
        opted_in=True,
        created_at=datetime.now(timezone.utc),
    )
    lesson = Lesson(
        lesson_id=1,
        title="Nothing I see means anything",
        content="Lesson one content.",
        created_at=datetime.now(timezone.utc),
    )
    session.add(user)
    session.add(lesson)
    session.commit()

    yield session
    session.close()


@pytest.fixture(scope="function")
def scheduler_session_factory(db_session, monkeypatch):
    Session = sessionmaker(bind=db_session.get_bind())
    monkeypatch.setattr(scheduler_module, "SessionLocal", Session)
    return Session


def test_execute_scheduled_task_sends_lesson_one(db_session, scheduler_session_factory, monkeypatch):
    sent = []

    async def fake_send_message(chat_id: int, text: str):
        sent.append((chat_id, text))
        return {"ok": True}

    monkeypatch.setattr(scheduler_module, "send_message", fake_send_message)

    user = db_session.query(User).first()
    schedule = Schedule(
        user_id=user.user_id,
        lesson_id=None,
        schedule_type="daily",
        cron_expression="0 9 * * *",
        next_send_time=datetime.now(timezone.utc),
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(schedule)
    db_session.commit()

    scheduler_module.SchedulerService.execute_scheduled_task(schedule.schedule_id)

    db_session.refresh(schedule)
    assert sent, "Expected lesson message to be sent"
    assert "Lesson 1" in sent[0][1]

    memory = db_session.query(Memory).filter_by(key="last_sent_lesson_id").first()
    assert memory is not None
    assert memory.value == "1"

    log = db_session.query(MessageLog).filter_by(direction="outbound").first()
    assert log is not None
    assert "Lesson 1" in log.content


def test_execute_scheduled_task_prompts_confirmation(db_session, scheduler_session_factory, monkeypatch):
    sent = []

    async def fake_send_message(chat_id: int, text: str):
        sent.append((chat_id, text))
        return {"ok": True}

    monkeypatch.setattr(scheduler_module, "send_message", fake_send_message)

    user = db_session.query(User).first()
    schedule = Schedule(
        user_id=user.user_id,
        lesson_id=None,
        schedule_type="daily",
        cron_expression="0 9 * * *",
        next_send_time=datetime.now(timezone.utc),
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(schedule)
    db_session.commit()

    # Simulate last sent lesson
    memory = Memory(
        user_id=user.user_id,
        category="progress",
        key="last_sent_lesson_id",
        value="1",
        value_hash="",
        confidence=1.0,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(memory)
    db_session.commit()

    scheduler_module.SchedulerService.execute_scheduled_task(schedule.schedule_id)

    assert sent, "Expected confirmation prompt to be sent"
    # Accept any confirmation prompt that references Lesson 1 (phrasing may vary)
    assert "Lesson 1" in sent[0][1]

    pending = db_session.query(Memory).filter_by(key="lesson_confirmation_pending").first()
    assert pending is not None


def test_deactivate_user_schedules(db_session, scheduler_session_factory, monkeypatch):
    removed = []

    class FakeScheduler:
        def remove_job(self, job_id: str):
            removed.append(job_id)

    monkeypatch.setattr(
        scheduler_module.SchedulerService,
        "get_scheduler",
        staticmethod(lambda: FakeScheduler()),
    )

    user = db_session.query(User).first()
    schedule = Schedule(
        user_id=user.user_id,
        lesson_id=None,
        schedule_type="daily",
        cron_expression="0 9 * * *",
        next_send_time=datetime.now(timezone.utc),
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(schedule)
    db_session.commit()

    deactivated = scheduler_module.SchedulerService.deactivate_user_schedules(user.user_id)

    db_session.refresh(schedule)
    assert deactivated == 1
    assert schedule.is_active is False
    assert removed == [f"schedule_{schedule.schedule_id}"]