import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import (
    Base,
    User,
    Memory,
    MessageLog,
    Schedule,
    Unsubscribe,
)
from src.services.gdpr_service import (
    export_user_data,
    restrict_processing,
    rectify_user,
    erase_user_data,
    record_consent,
)


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _create_user(session):
    user = User(
        external_id="gdpr-1",
        channel="test",
        first_name="Test",
        last_name="User",
        email="test@example.com",
        phone_number="+4712345678",
        opted_in=True,
        created_at=datetime.datetime.utcnow(),
    )
    session.add(user)
    session.commit()
    return user


def _create_memory(session, user_id: int):
    memory = Memory(
        user_id=user_id,
        category="profile",
        key="favorite_color",
        value="blue",
        confidence=0.9,
        is_active=True,
        source="test",
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
    )
    session.add(memory)
    session.commit()
    return memory


def _create_message(session, user_id: int):
    message = MessageLog(
        user_id=user_id,
        direction="inbound",
        channel="test",
        content="hello",
        status="delivered",
        created_at=datetime.datetime.utcnow(),
    )
    session.add(message)
    session.commit()
    return message


def _create_schedule(session, user_id: int):
    schedule = Schedule(
        user_id=user_id,
        lesson_id=None,
        schedule_type="daily",
        cron_expression="0 9 * * *",
        is_active=True,
        created_at=datetime.datetime.utcnow(),
    )
    session.add(schedule)
    session.commit()
    return schedule


def _create_unsubscribe(session, user_id: int):
    unsubscribe = Unsubscribe(
        user_id=user_id,
        channel="test",
        reason="user request",
        compliance_required=False,
        unsubscribed_at=datetime.datetime.utcnow(),
    )
    session.add(unsubscribe)
    session.commit()
    return unsubscribe


def test_gdpr_export_restrict_rectify_erase(db_session):
    user = _create_user(db_session)
    memory = _create_memory(db_session, user.user_id)
    _create_message(db_session, user.user_id)
    _create_schedule(db_session, user.user_id)
    _create_unsubscribe(db_session, user.user_id)

    record_consent(
        db_session,
        user_id=user.user_id,
        scope="data_storage",
        granted=True,
        source="test",
    )

    export = export_user_data(db_session, user.user_id)
    assert export["schema_version"] == 1
    assert export["user"]["user_id"] == user.user_id
    assert len(export["memories"]) == 1

    restrict_processing(db_session, user.user_id, reason="test", actor="tester")
    refreshed = db_session.query(User).filter_by(user_id=user.user_id).first()
    assert refreshed.processing_restricted is True
    assert refreshed.opted_in is False
    assert refreshed.restriction_reason == "test"

    rectify_user(
        db_session,
        user.user_id,
        updates={"first_name": "Fixed"},
        memory_updates=[{"memory_id": memory.memory_id, "value": "green"}],
        actor="tester",
    )
    updated = db_session.query(User).filter_by(user_id=user.user_id).first()
    updated_memory = db_session.query(Memory).filter_by(memory_id=memory.memory_id).first()
    assert updated.first_name == "Fixed"
    assert updated_memory.value == "green"

    erase_user_data(db_session, user.user_id, reason="test", actor="tester")
    erased = db_session.query(User).filter_by(user_id=user.user_id).first()
    assert erased.is_deleted is True
    assert erased.processing_restricted is True
    assert erased.opted_in is False
    assert erased.first_name is None
    assert db_session.query(Memory).filter_by(user_id=user.user_id).count() == 0
    assert db_session.query(MessageLog).filter_by(user_id=user.user_id).count() == 0
    assert db_session.query(Schedule).filter_by(user_id=user.user_id).count() == 0
