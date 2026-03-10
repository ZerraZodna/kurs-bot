"""
Migrated integration tests for GDPR API.
 migrated from tests/test_gdpr_api.py
"""
import datetime

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.config import settings
from src.models.database import (
    User,
    Memory,
    MessageLog,
    Schedule,
    Unsubscribe,
)
from src.services.gdpr_service import record_consent
from tests.fixtures.database import db_session


@pytest.fixture
def client():
    """Create a test client for the API."""
    with TestClient(app) as c:
        yield c


def _seed_user(db_session) -> int:
    """Seed a test user with data."""
    user = User(
        external_id="gdpr-api-1",
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
    db_session.refresh(user)

    memory = Memory(
        user_id=user.user_id,
        category="profile",
        key="favorite_color",
        value="blue",
        is_active=True,
        source="test",
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
    )
    db_session.add(memory)

    message = MessageLog(
        user_id=user.user_id,
        direction="inbound",
        channel="test",
        content="hello",
        status="delivered",
        created_at=datetime.datetime.utcnow(),
    )
    db_session.add(message)

    schedule = Schedule(
        user_id=user.user_id,
        lesson_id=None,
        schedule_type="daily",
        cron_expression="0 9 * * *",
        is_active=True,
        created_at=datetime.datetime.utcnow(),
    )
    db_session.add(schedule)

    unsubscribe = Unsubscribe(
        user_id=user.user_id,
        channel="test",
        reason="user request",
        compliance_required=False,
        unsubscribed_at=datetime.datetime.utcnow(),
    )
    db_session.add(unsubscribe)
    db_session.commit()

    record_consent(
        db_session,
        user_id=user.user_id,
        scope="data_storage",
        granted=True,
        source="test",
    )
    return user.user_id


def test_gdpr_endpoints_require_token(client, db_session):
    """Given: A request to GDPR endpoints without proper authentication
    When: No token or wrong token is provided
    Then: Returns 401 or 403 respectively
    """
    # Given: User exists in database
    user_id = _seed_user(db_session)
    settings.GDPR_ADMIN_TOKEN = "test-token"

    # When: Request without token
    response = client.post("/gdpr/export", json={"user_id": user_id})
    assert response.status_code == 401

    # When: Request with wrong token
    response = client.post(
        "/gdpr/export",
        json={"user_id": user_id},
        headers={"X-GDPR-Token": "bad"},
    )
    assert response.status_code == 403


def test_gdpr_export_restrict_rectify_erase_api(client, db_session):
    """Given: A user with data in the system
    When: GDPR export, restrict, rectify, erase operations are called via API
    Then: Operations are performed correctly
    """
    # Given: User with data
    user_id = _seed_user(db_session)
    settings.GDPR_ADMIN_TOKEN = "test-token"
    headers = {"X-GDPR-Token": settings.GDPR_ADMIN_TOKEN}

    # When: Export user data
    export = client.post("/gdpr/export", json={"user_id": user_id}, headers=headers)
    assert export.status_code == 200
    payload = export.json()
    assert payload["schema_version"] == 1
    assert payload["user"]["user_id"] == user_id

    # When: Restrict processing
    restrict = client.post(
        "/gdpr/restrict",
        json={"user_id": user_id, "reason": "test", "actor": "tester"},
        headers=headers,
    )
    assert restrict.status_code == 200
    assert restrict.json()["status"] == "restricted"

    # Then: User should be restricted - create new session to see API changes
    from src.models.database import SessionLocal
    verify_session = SessionLocal()
    try:
        user = verify_session.query(User).filter_by(user_id=user_id).first()
        memory = verify_session.query(Memory).filter_by(user_id=user_id).first()
        assert user.processing_restricted is True
        assert user.opted_in is False
        assert memory is not None
    finally:
        verify_session.close()

    # When: Rectify user data
    rectify = client.post(
        "/gdpr/rectify",
        json={
            "user_id": user_id,
            "updates": {"first_name": "Fixed"},
            "memory_updates": [{"memory_id": memory.memory_id, "value": "green"}],
            "actor": "tester",
        },
        headers=headers,
    )
    assert rectify.status_code == 200
    assert rectify.json()["status"] == "rectified"

    # Then: Data should be updated - create new session to see API changes
    verify_session2 = SessionLocal()
    try:
        updated = verify_session2.query(User).filter_by(user_id=user_id).first()
        updated_memory = verify_session2.query(Memory).filter_by(user_id=user_id).first()
        assert updated.first_name == "Fixed"
        assert updated_memory.value == "green"
    finally:
        verify_session2.close()

    # When: Erase user data
    erase = client.post(
        "/gdpr/erase",
        json={"user_id": user_id, "reason": "test", "actor": "tester"},
        headers=headers,
    )
    assert erase.status_code == 200
    assert erase.json()["status"] == "erased"

    # Then: User data should be erased - create new session to see API changes
    verify_session3 = SessionLocal()
    try:
        erased = verify_session3.query(User).filter_by(user_id=user_id).first()
        assert erased.is_deleted is True
        assert erased.processing_restricted is True
        assert erased.opted_in is False
        assert verify_session3.query(Memory).filter_by(user_id=user_id).count() == 0
        assert verify_session3.query(MessageLog).filter_by(user_id=user_id).count() == 0
        assert verify_session3.query(Schedule).filter_by(user_id=user_id).count() == 0
    finally:
        verify_session3.close()


def test_gdpr_object_and_withdraw_consent_api(client, db_session):
    """Given: A user with consent
    When: Objecting to processing and withdrawing consent via API
    Then: Operations are performed correctly
    """
    # Given: User with consent
    user_id = _seed_user(db_session)
    settings.GDPR_ADMIN_TOKEN = "test-token"
    headers = {"X-GDPR-Token": settings.GDPR_ADMIN_TOKEN}

    # When: Object to processing
    obj = client.post(
        "/gdpr/object",
        json={"user_id": user_id, "reason": "marketing", "actor": "tester"},
        headers=headers,
    )
    assert obj.status_code == 200
    assert obj.json()["status"] == "objected"

    # Then: User should be restricted - create new session to see API changes
    from src.models.database import SessionLocal
    verify_session = SessionLocal()
    try:
        user = verify_session.query(User).filter_by(user_id=user_id).first()
        assert user.processing_restricted is True
        assert user.opted_in is False
    finally:
        verify_session.close()

    # When: Withdraw consent
    withdraw = client.post(
        "/gdpr/withdraw-consent",
        json={"user_id": user_id, "scope": "data_storage", "actor": "tester"},
        headers=headers,
    )
    assert withdraw.status_code == 200
    assert withdraw.json()["status"] == "withdrawn"


def test_gdpr_privacy_notice_public(client):
    """Given: A request to the privacy notice endpoint
    When: Any user accesses the endpoint
    Then: The privacy notice is returned
    """
    # When: Accessing privacy notice
    response = client.get("/gdpr/privacy-notice")
    assert response.status_code == 200
    assert "Privacy Notice" in response.json().get("content", "")

