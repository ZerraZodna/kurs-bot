import pytest
from fastapi.testclient import TestClient
from src.api.app import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_webhook_forbidden(client):
    # Wrong token should return 403
    response = client.post("/webhook/telegram/wrongtoken", json={})
    assert response.status_code == 403

def test_webhook_invalid_payload(client):
    # Correct token, but invalid payload (no message)
    from src.config import settings
    token_suffix = settings.TELEGRAM_BOT_TOKEN.split(":")[1]
    response = client.post(f"/webhook/telegram/{token_suffix}", json={"update_id": 1})
    assert response.status_code == 200
    assert response.json()["ok"] is False

