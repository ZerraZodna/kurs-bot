"""
Migrated tests for GDPR service.
 migrated from tests/test_gdpr.py
"""
import datetime


from src.models.database import (
    User,
    Memory,
    MessageLog,
    Schedule,
)
from src.services.maintenance import purge_expired_ttl_memories
from src.services.gdpr_service import (
    export_user_data,
    restrict_processing,
    object_to_processing,
    rectify_user,
    erase_user_data,
    record_consent,
    withdraw_consent,
)


def _create_user(db_session):
    """Helper to create a test user."""
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
    db_session.add(user)
    db_session.commit()
    return user


def _create_memory(session, user_id: int):
    """Helper to create a test memory."""
    memory = Memory(
        user_id=user_id,
        category="profile",
        key="favorite_color",
        value="blue",
        is_active=True,
        source="test",
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
    )
    session.add(memory)
    session.commit()
    return memory


def _create_message(session, user_id: int):
    """Helper to create a test message log."""
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
    """Helper to create a test schedule."""
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

def test_gdpr_export_restrict_rectify_erase(db_session):
    """Given: A user with memories, messages, schedules, and unsubscribes
    When: GDPR operations are performed (export, restrict, rectify, erase)
    Then: Data is correctly exported and processed
    """
    # Given: User with data
    user = _create_user(db_session)
    memory = _create_memory(db_session, user.user_id)
    _create_message(db_session, user.user_id)
    _create_schedule(db_session, user.user_id)

    record_consent(
        db_session,
        user_id=user.user_id,
        scope="data_storage",
        granted=True,
        source="test",
    )

    # When: Export user data
    export = export_user_data(db_session, user.user_id)
    assert export["schema_version"] == 1
    assert export["user"]["user_id"] == user.user_id
    assert len(export["memories"]) == 1

    # When: Restrict processing
    restrict_processing(db_session, user.user_id, reason="test", actor="tester")
    refreshed = db_session.query(User).filter_by(user_id=user.user_id).first()
    assert refreshed.processing_restricted is True
    assert refreshed.opted_in is False
    assert refreshed.restriction_reason == "test"

    # When: Rectify user data
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

    # When: Erase user data
    erase_user_data(db_session, user.user_id, reason="test", actor="tester")
    erased = db_session.query(User).filter_by(user_id=user.user_id).first()
    assert erased.is_deleted is True
    assert erased.processing_restricted is True
    assert erased.opted_in is False
    assert erased.first_name is None
    assert db_session.query(Memory).filter_by(user_id=user.user_id).count() == 0
    assert db_session.query(MessageLog).filter_by(user_id=user.user_id).count() == 0
    assert db_session.query(Schedule).filter_by(user_id=user.user_id).count() == 0


def test_gdpr_retention_purges_ttl_memories(db_session):
    """Given: A user with an expired TTL memory
    When: purge_expired_ttl_memories is called
    Then: The expired memory is deleted
    """
    # Given: User with expired memory
    user = _create_user(db_session)
    expired = Memory(
        user_id=user.user_id,
        category="profile",
        key="temp",
        value="old",
        is_active=True,
        source="test",
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
        ttl_expires_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
    )
    db_session.add(expired)
    db_session.commit()

    # When: Purging expired TTL memories
    deleted = purge_expired_ttl_memories(session=db_session)
    
    # Then: Memory should be deleted
    assert deleted == 1
    assert db_session.query(Memory).filter_by(user_id=user.user_id).count() == 0


def test_gdpr_object_and_withdraw_consent(db_session):
    """Given: A user with consent
    When: Objecting to processing and withdrawing consent
    Then: User's processing is restricted and consent is withdrawn
    """
    # Given: User with consent
    user = _create_user(db_session)

    # When: Objecting to processing
    object_to_processing(db_session, user.user_id, reason="marketing", actor="tester")
    refreshed = db_session.query(User).filter_by(user_id=user.user_id).first()
    assert refreshed.processing_restricted is True
    assert refreshed.opted_in is False

    # When: Withdrawing consent
    withdraw_consent(
        db_session,
        user_id=user.user_id,
        scope="data_storage",
        actor="tester",
        reason="user request",
    )
    refreshed = db_session.query(User).filter_by(user_id=user.user_id).first()
    assert refreshed.processing_restricted is True
    assert refreshed.opted_in is False

