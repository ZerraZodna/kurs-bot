import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base, User, Lesson, Schedule
from src.services.scheduler import manager


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # seed user and lesson
    user = User(external_id="mngr", channel="telegram", first_name="Mgr", last_name="Test", opted_in=True, created_at=datetime.datetime.utcnow())
    lesson = Lesson(title="L", content="C", created_at=datetime.datetime.utcnow())
    session.add(user)
    session.add(lesson)
    session.commit()
    yield session
    session.close()


def test_create_get_update_deactivate(db_session):
    user = db_session.query(User).first()
    lesson = db_session.query(Lesson).first()

    # create
    sched = manager.create_schedule(
        user_id=user.user_id,
        lesson_id=lesson.lesson_id,
        schedule_type="daily",
        cron_expression="0 9 * * *",
        next_send_time=datetime.datetime.utcnow(),
        session=db_session,
    )
    assert sched.schedule_id is not None

    # get
    schedules = manager.get_user_schedules(user.user_id, active_only=True, session=db_session)
    assert len(schedules) == 1

    # update
    updated = manager.update_schedule(sched.schedule_id, {"cron_expression": "0 10 * * *"}, session=db_session)
    assert updated is not None
    assert updated.cron_expression == "0 10 * * *"

    # deactivate
    ok = manager.deactivate_schedule(sched.schedule_id, session=db_session)
    assert ok is True
    s = db_session.query(Schedule).filter_by(schedule_id=sched.schedule_id).first()
    assert s.is_active is False


def test_find_active_daily_and_deactivate_user(db_session):
    user = db_session.query(User).first()

    # create two schedules, one active daily and one inactive
    s1 = manager.create_schedule(user_id=user.user_id, lesson_id=None, schedule_type="daily", cron_expression="0 8 * * *", session=db_session)
    s2 = manager.create_schedule(user_id=user.user_id, lesson_id=None, schedule_type="daily", cron_expression="0 7 * * *", session=db_session)

    found = manager.find_active_daily_schedule(user.user_id, session=db_session)
    assert found is not None

    # deactivate all
    count = manager.deactivate_user_schedules(user.user_id, session=db_session)
    assert count == 2
