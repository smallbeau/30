import pytest
from fastapi.testclient import TestClient

from app.main import app, verify_token


@pytest.fixture()
def client():
    return TestClient(app)


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "version" in body
    assert "service" in body


def test_server_header(client):
    r = client.get("/health")
    assert "x-process-time" in r.headers
    assert r.headers["server"] == "voice-assistant/1.0"


def test_no_api_key_allows_all(client):
    r = client.get("/api/voice/pipeline")
    assert r.status_code == 200
