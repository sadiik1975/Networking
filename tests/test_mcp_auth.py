from fastapi.testclient import TestClient

from app.config import settings
from app.mcp_auth import McpAuthMiddleware


async def _ok_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def _client(monkeypatch, key):
    monkeypatch.setattr(settings, "mcp_api_key", key)
    return TestClient(McpAuthMiddleware(_ok_app))


def test_rejects_when_key_not_configured(monkeypatch):
    assert _client(monkeypatch, None).get("/").status_code == 503


def test_rejects_missing_or_wrong_key(monkeypatch):
    client = _client(monkeypatch, "secret")
    assert client.get("/").status_code == 401
    assert client.get("/", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_accepts_bearer_and_x_api_key(monkeypatch):
    client = _client(monkeypatch, "secret")
    assert client.get("/", headers={"Authorization": "Bearer secret"}).status_code == 200
    assert client.get("/", headers={"X-API-Key": "secret"}).status_code == 200


def test_mounted_mcp_requires_auth(monkeypatch):
    from app.main import app

    monkeypatch.setattr(settings, "mcp_api_key", "secret")
    assert TestClient(app).get("/mcp/sse").status_code == 401
