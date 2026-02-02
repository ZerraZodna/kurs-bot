import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.database import Base, Schedule, User, Lesson
import datetime

@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # Add a user and lesson for FK
    user = User(external_id="99999", channel="telegram", first_name="Sched", last_name="Test", opted_in=True, created_at=datetime.datetime.utcnow())
    lesson = Lesson(title="Test Lesson", content="Content", created_at=datetime.datetime.utcnow())
    session.add(user)
    session.add(lesson)
    session.commit()
    yield session
    session.close()

def test_schedule_crud(db_session):
    user = db_session.query(User).first()
    lesson = db_session.query(Lesson).first()
    # Create
    sched = Schedule(
        user_id=user.user_id,
        lesson_id=lesson.lesson_id,
        schedule_type="daily",
        cron_expression="0 8 * * *",
        is_active=True,
        created_at=datetime.datetime.utcnow()
    )
    db_session.add(sched)
    db_session.commit()
    assert sched.schedule_id is not None

    # Read
    fetched = db_session.query(Schedule).filter_by(schedule_type="daily").first()
    assert fetched.cron_expression == "0 8 * * *"

    # Update
    fetched.cron_expression = "0 9 * * *"
    db_session.commit()
    updated = db_session.query(Schedule).filter_by(schedule_id=sched.schedule_id).first()
    assert updated.cron_expression == "0 9 * * *"

    # Delete
    db_session.delete(updated)
    db_session.commit()
    assert db_session.query(Schedule).filter_by(schedule_id=sched.schedule_id).first() is None
