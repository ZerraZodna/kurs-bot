import pytest
from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_webhook_forbidden():
    # Wrong token should return 403
    response = client.post("/webhook/telegram/wrongtoken", json={})
    assert response.status_code == 403

def test_webhook_invalid_payload():
    # Correct token, but invalid payload (no message)
    from src.config import settings
    token_suffix = settings.TELEGRAM_BOT_TOKEN.split(":")[1]
    response = client.post(f"/webhook/telegram/{token_suffix}", json={"update_id": 1})
    assert response.status_code == 200
    assert response.json()["ok"] is False

def test_webhook_valid_message(monkeypatch):
    # Patch DB and MessageLog to avoid real DB writes
    from src.config import settings
    token_suffix = settings.TELEGRAM_BOT_TOKEN.split(":")[1]
    payload = {
        "message": {
            "message_id": 123,
            "from": {"id": 42, "first_name": "John", "last_name": "Doe"},
            "text": "Hello!",
            "date": 1700000000
        }
    }
    # Patch SessionLocal and MessageLog
    import src.api.app as app_module
    class DummyUser:
        def __init__(self):
            self.user_id = 1
            self.first_name = "John"
            self.last_name = "Doe"
    class DummyDB:
        def query(self, *a, **kw):
            class DummyQuery:
                def filter_by(self, *a, **kw):
                    return self
                def first(self):
                    return DummyUser()
            return DummyQuery()
        def add(self, *a, **kw): pass
        def commit(self): pass
        def close(self): pass
    monkeypatch.setattr(app_module, "SessionLocal", lambda: DummyDB())
    monkeypatch.setattr(app_module, "MessageLog", lambda **kwargs: None)
    response = client.post(f"/webhook/telegram/{token_suffix}", json=payload)
    assert response.status_code == 200
    assert response.json()["ok"] is True
