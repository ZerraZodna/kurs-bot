"""
Migrated tests for SchedulerService.
 migrated from tests/test_scheduler_service.py
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base, User, Lesson, Schedule, Memory, MessageLog
from src import scheduler as scheduler_module


@pytest.fixture(scope="function")
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create test user
    user = User(
        external_id="99999",
        channel="telegram",
        first_name="Sched",
        last_name="Test",
        opted_in=True,
        created_at=datetime.now(timezone.utc),
    )
    
    # Create test lessons
    lesson = Lesson(
        lesson_id=1,
        title="Nothing I see means anything",
        content="Lesson one content.",
        created_at=datetime.now(timezone.utc),
    )
    lesson_two = Lesson(
        lesson_id=2,
        title="I have given everything I see all the meaning that it has for me",
        content="Lesson two content.",
        created_at=datetime.now(timezone.utc),
    )
    session.add(user)
    session.add(lesson)
    session.add(lesson_two)
    session.commit()

    yield session
    session.close()


@pytest.fixture(scope="function")
def scheduler_session_factory(db_session, monkeypatch):
    """Patch the scheduler module to use the test database session."""
    Session = sessionmaker(bind=db_session.get_bind())
    monkeypatch.setattr(scheduler_module, "SessionLocal", Session)
    return Session


class TestSchedulerService:
    """Tests for SchedulerService functionality."""

    def test_execute_scheduled_task_sends_lesson_one(
        self, db_session, scheduler_session_factory, monkeypatch
    ):
        """Given: A user with an active daily schedule
        When: execute_scheduled_task is called
        Then: Lesson 1 message is sent
        """
        sent = []

        async def fake_send_message(chat_id: int, text: str):
            sent.append((chat_id, text))
            return {"ok": True}

        monkeypatch.setattr(scheduler_module, "send_message", fake_send_message)

        # Given: User with active daily schedule
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

        # When: Executing the scheduled task
        scheduler_module.SchedulerService.execute_scheduled_task(schedule.schedule_id)

        # Then: Lesson message should be sent
        db_session.refresh(schedule)
        assert sent, "Expected lesson message to be sent"
        assert "Lesson 1" in sent[0][1]

        # Verify last sent was persisted
        from src.memories import MemoryManager
        from src.lessons.state import get_last_sent_lesson_id

        mm = MemoryManager(db_session)
        last_sent = get_last_sent_lesson_id(mm, user.user_id)
        assert last_sent == 1

        # Verify message log was created
        log = db_session.query(MessageLog).filter_by(direction="outbound").first()
        assert log is not None
        assert "Lesson 1" in log.content

    def test_execute_scheduled_task_prompts_confirmation(
        self, db_session, scheduler_session_factory, monkeypatch
    ):
        """Given: User has already received lesson 1
        When: execute_scheduled_task is called
        Then: Confirmation prompt for lesson 2 is sent
        """
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

        # Given: Last sent lesson is 1
        from src.memories import MemoryManager
        from src.lessons.state import set_last_sent_lesson_id

        mm = MemoryManager(db_session)
        set_last_sent_lesson_id(mm, user.user_id, 1)

        # When: Executing scheduled task
        scheduler_module.SchedulerService.execute_scheduled_task(schedule.schedule_id)

        # Then: Confirmation prompt should be sent
        assert sent, "Expected confirmation prompt to be sent"
        assert "Lesson 1" in sent[0][1]

        pending = db_session.query(Memory).filter_by(key="lesson_confirmation_pending").first()
        assert pending is not None

    def test_execute_scheduled_task_auto_advance_skips_confirmation_when_preference_enabled(
        self, db_session, scheduler_session_factory, monkeypatch
    ):
        """Given: User has auto-advance preference enabled
        When: execute_scheduled_task is called
        Then: Next lesson is sent without confirmation prompt
        """
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

        # Given: Last sent is lesson 1 and auto-advance is enabled
        from src.memories import MemoryManager
        from src.lessons.state import set_last_sent_lesson_id, get_last_sent_lesson_id
        from src.scheduler.memory_helpers import set_auto_advance_lessons_preference

        mm = MemoryManager(db_session)
        set_last_sent_lesson_id(mm, user.user_id, 1)
        set_auto_advance_lessons_preference(mm, user.user_id, True, source="test")

        # When: Executing scheduled task
        scheduler_module.SchedulerService.execute_scheduled_task(schedule.schedule_id)

        # Then: Next lesson should be sent without confirmation
        assert sent, "Expected next lesson message to be sent"
        assert "Lesson 2" in sent[0][1]

        pending = db_session.query(Memory).filter_by(key="lesson_confirmation_pending").first()
        assert pending is None

        completed = db_session.query(Memory).filter_by(key="lesson_completed").first()
        assert completed is not None
        assert completed.value == "1"

        assert get_last_sent_lesson_id(mm, user.user_id) == 2

    def test_deactivate_user_schedules(
        self, db_session, scheduler_session_factory, monkeypatch
    ):
        """Given: User has active schedules
        When: deactivate_user_schedules is called
        Then: All schedules are deactivated
        """
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

        # When
        deactivated = scheduler_module.SchedulerService.deactivate_user_schedules(user.user_id)

        # Then
        db_session.refresh(schedule)
        assert deactivated == 1
        assert schedule.is_active is False
        assert removed == [f"schedule_{schedule.schedule_id}"]

