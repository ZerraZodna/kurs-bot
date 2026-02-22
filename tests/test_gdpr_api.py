import datetime

from fastapi.testclient import TestClient

from src.api.app import app
from src.config import settings
from src.models.database import (
    Base,
    SessionLocal,
    engine,
    User,
    Memory,
    MessageLog,
    Schedule,
    Unsubscribe,
    ConsentLog,
    GdprRequest,
    GdprAuditLog,
)
from src.memories.memory_handler import MemoryHandler
from src.services.gdpr_service import record_consent


import pytest


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _reset_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(GdprAuditLog).delete()
        db.query(GdprRequest).delete()
        db.query(ConsentLog).delete()
        db.query(Unsubscribe).delete()
        db.query(MessageLog).delete()
        db.query(Schedule).delete()
        MemoryHandler(db).delete_all_memories()
        db.query(User).delete()
        db.commit()
    finally:
        db.close()


def _seed_user() -> int:
    db = SessionLocal()
    try:
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
        db.add(user)
        db.commit()
        db.refresh(user)

        memory = Memory(
            user_id=user.user_id,
            category="profile",
            key="favorite_color",
            value="blue",
            confidence=0.9,
            is_active=True,
            source="test",
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
        )
        db.add(memory)

        message = MessageLog(
            user_id=user.user_id,
            direction="inbound",
            channel="test",
            content="hello",
            status="delivered",
            created_at=datetime.datetime.utcnow(),
        )
        db.add(message)

        schedule = Schedule(
            user_id=user.user_id,
            lesson_id=None,
            schedule_type="daily",
            cron_expression="0 9 * * *",
            is_active=True,
            created_at=datetime.datetime.utcnow(),
        )
        db.add(schedule)

        unsubscribe = Unsubscribe(
            user_id=user.user_id,
            channel="test",
            reason="user request",
            compliance_required=False,
            unsubscribed_at=datetime.datetime.utcnow(),
        )
        db.add(unsubscribe)
        db.commit()

        record_consent(
            db,
            user_id=user.user_id,
            scope="data_storage",
            granted=True,
            source="test",
        )
        return user.user_id
    finally:
        db.close()


def test_gdpr_endpoints_require_token(client):
    _reset_db()
    user_id = _seed_user()
    settings.GDPR_ADMIN_TOKEN = "test-token"

    response = client.post("/gdpr/export", json={"user_id": user_id})
    assert response.status_code == 401

    response = client.post(
        "/gdpr/export",
        json={"user_id": user_id},
        headers={"X-GDPR-Token": "bad"},
    )
    assert response.status_code == 403


def test_gdpr_export_restrict_rectify_erase_api(client):
    _reset_db()
    user_id = _seed_user()
    settings.GDPR_ADMIN_TOKEN = "test-token"
    headers = {"X-GDPR-Token": settings.GDPR_ADMIN_TOKEN}

    export = client.post("/gdpr/export", json={"user_id": user_id}, headers=headers)
    assert export.status_code == 200
    payload = export.json()
    assert payload["schema_version"] == 1
    assert payload["user"]["user_id"] == user_id

    restrict = client.post(
        "/gdpr/restrict",
        json={"user_id": user_id, "reason": "test", "actor": "tester"},
        headers=headers,
    )
    assert restrict.status_code == 200
    assert restrict.json()["status"] == "restricted"

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(user_id=user_id).first()
        memory = db.query(Memory).filter_by(user_id=user_id).first()
        assert user.processing_restricted is True
        assert user.opted_in is False
        assert memory is not None
    finally:
        db.close()

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

    db = SessionLocal()
    try:
        updated = db.query(User).filter_by(user_id=user_id).first()
        updated_memory = db.query(Memory).filter_by(user_id=user_id).first()
        assert updated.first_name == "Fixed"
        assert updated_memory.value == "green"
    finally:
        db.close()

    erase = client.post(
        "/gdpr/erase",
        json={"user_id": user_id, "reason": "test", "actor": "tester"},
        headers=headers,
    )
    assert erase.status_code == 200
    assert erase.json()["status"] == "erased"

    db = SessionLocal()
    try:
        erased = db.query(User).filter_by(user_id=user_id).first()
        assert erased.is_deleted is True
        assert erased.processing_restricted is True
        assert erased.opted_in is False
        assert db.query(Memory).filter_by(user_id=user_id).count() == 0
        assert db.query(MessageLog).filter_by(user_id=user_id).count() == 0
        assert db.query(Schedule).filter_by(user_id=user_id).count() == 0
    finally:
        db.close()


def test_gdpr_object_and_withdraw_consent_api(client):
    _reset_db()
    user_id = _seed_user()
    settings.GDPR_ADMIN_TOKEN = "test-token"
    headers = {"X-GDPR-Token": settings.GDPR_ADMIN_TOKEN}

    obj = client.post(
        "/gdpr/object",
        json={"user_id": user_id, "reason": "marketing", "actor": "tester"},
        headers=headers,
    )
    assert obj.status_code == 200
    assert obj.json()["status"] == "objected"

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(user_id=user_id).first()
        assert user.processing_restricted is True
        assert user.opted_in is False
    finally:
        db.close()

    withdraw = client.post(
        "/gdpr/withdraw-consent",
        json={"user_id": user_id, "scope": "data_storage", "actor": "tester"},
        headers=headers,
    )
    assert withdraw.status_code == 200
    assert withdraw.json()["status"] == "withdrawn"


def test_gdpr_privacy_notice_public(client):
    response = client.get("/gdpr/privacy-notice")
    assert response.status_code == 200
    assert "Privacy Notice" in response.json().get("content", "")
