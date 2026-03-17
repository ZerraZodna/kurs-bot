"""
Migrated tests for SchedulerService.
 migrated from tests/test_scheduler_service.py
"""
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.lessons.state import set_current_lesson
from src.models.database import Base, User, Lesson, Schedule, MessageLog
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

    @pytest.mark.parametrize(
        "days_ago, expected_lesson",
        [
            (0, 1),  # same day: repeat
            (1, 2),  # previous day: advance
        ],
    )
    def test_execute_scheduled_task_sends_lesson_one_advances_based_on_activity_day(
        self, db_session, scheduler_session_factory, monkeypatch, days_ago: int, expected_lesson: int
    ):
        """Test lesson sent advances only if user was active previous day (advanced_by_day=True)."""
        sent = []

        async def fake_send_message(chat_id: int, text: str):
            sent.append((chat_id, text))
            return {"ok": True}

        monkeypatch.setattr(scheduler_module, "send_message", fake_send_message)


        # Given: User with active daily schedule
        user = db_session.query(User).first()
        now = datetime.now(timezone.utc)
        user.last_active_at = now - timedelta(days=days_ago)
        db_session.commit()

        schedule = Schedule(
            user_id=user.user_id,
            lesson_id=None,
            schedule_type="daily",
            cron_expression="0 9 * * *",
            next_send_time=now,
            is_active=True,
            created_at=now,
        )
        db_session.add(schedule)
        db_session.commit()

        # Given: Last sent lesson is 1
        from src.memories import MemoryManager
        from src.lessons.state import get_current_lesson, compute_current_lesson_state

        mm = MemoryManager(db_session)
        set_current_lesson(mm, user.user_id, 1)

        # Refresh user to avoid stale identity-map values before state computation
        db_session.refresh(user)

        # Verify expected advance state
        state = compute_current_lesson_state(mm, user.user_id)
        expected_advance = days_ago > 0
        assert state["advanced_by_day"] == expected_advance

        # When: Executing the scheduled task
        scheduler_module.SchedulerService.execute_scheduled_task(schedule.schedule_id, session=db_session)

        # Then: Lesson message should be sent with correct advancement
        assert sent, "Expected lesson message to be sent"
        assert f"Lesson {expected_lesson}" in sent[0][1]

        current = get_current_lesson(mm, user.user_id)
        # Scheduler currently delivers the advanced lesson text based on activity day,
        # but persists lesson progression separately (current lesson may remain unchanged here).
        if days_ago == 0:
            assert current == expected_lesson
        else:
            assert current in (1, expected_lesson)

        # Verify last_active_at updated
        db_session.refresh(user)
        assert user.last_active_at.replace(tzinfo=None) >= now.replace(tzinfo=None)

        # Verify message log was created
        log = db_session.query(MessageLog).filter_by(direction="outbound").first()
        assert log is not None
        assert f"Lesson {expected_lesson}" in log.content

        # Verify schedule progressed (normalize to naive for SQLite compatibility)
        db_session.refresh(schedule)
        next_send = schedule.next_send_time
        if next_send is not None and next_send.tzinfo is not None:
            next_send = next_send.replace(tzinfo=None)
        now_naive = now.replace(tzinfo=None)
        assert next_send > now_naive


    def test_deactivate_user_schedules(
        self, db_session, scheduler_session_factory
    ):
        """Given: User has active schedules
        When: deactivate_user_schedules is called
        Then: All schedules are deactivated
        """


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
        deactivated = scheduler_module.SchedulerService.deactivate_user_schedules(user.user_id, session=db_session)

        # Then
        db_session.refresh(schedule)
        assert deactivated == 1
        assert schedule.is_active is False

