import json
from collections.abc import Iterator
from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import ask_agent, events
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import Contact, Event  # noqa: F401  (registers tables)


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    try:
        c = TestClient(app)
        c.headers.update({"X-API-Key": settings.api_key})
        yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


def soon(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def add(db: Session, title="Albany MWBE Forum", day=5, **kw):
    kw.setdefault("target_groups", ["MWBE"])
    return events.add_event(
        db, title, soon(day), kw.pop("state", "NY"), "in_person", "Host Org",
        kw.pop("url", "https://e.example/forum"), **kw,
    )


def test_ask_requires_key(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        c = TestClient(app)
        assert c.post("/ask", json={"question": "events?"}).status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_ask_board_mode_week(db, client, monkeypatch):
    monkeypatch.setattr(settings, "ai_api_key", None)
    add(db, day=3)
    add(db, title="Later Chamber Breakfast", day=40, target_groups=["Chamber_of_Commerce"])

    res = client.post("/ask", json={"question": "What's on my board this week?"})

    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "board"
    assert "Albany MWBE Forum" in body["answer"]
    assert "Later Chamber Breakfast" not in body["answer"]
    assert len(body["events"]) == 1


def test_ask_board_mode_mwbe_filter(db, client, monkeypatch):
    monkeypatch.setattr(settings, "ai_api_key", None)
    add(db, day=20)
    add(db, title="General B2B Night", day=20, target_groups=["B2B_Networking"])

    res = client.post("/ask", json={"question": "show mwbe"})

    body = res.json()
    assert "Albany MWBE Forum" in body["answer"]
    assert "General B2B Night" not in body["answer"]


def test_save_tool_refuses_without_confirmation(db):
    result, _ = ask_agent._exec_tool(db, "save_event", {
        "title": "Sneaky Event", "event_date": soon(9), "state": "NY",
        "event_format": "in_person", "organizer": "Org",
        "registration_url": "https://e.example/x", "confirmed": False,
    })
    assert "error" in result
    assert events.search_events(db)["count"] == 0

    result, _ = ask_agent._exec_tool(db, "save_event", {
        "title": "Confirmed Event", "event_date": soon(9), "state": "NY",
        "event_format": "in_person", "organizer": "Org",
        "registration_url": "https://e.example/y", "confirmed": True,
        "target_groups": ["MWBE"],
    })
    assert "saved" in result
    assert events.search_events(db)["count"] == 1


def test_ask_ai_mode_uses_search_tool(db, client, monkeypatch):
    monkeypatch.setattr(settings, "ai_api_key", "test-ai-key")
    add(db, day=10)
    calls = {"n": 0}
    real_post = httpx.Client.post

    def fake_post(self, url, **kwargs):
        if "chat/completions" not in str(url):
            return real_post(self, url, **kwargs)  # let the TestClient through
        calls["n"] += 1
        if calls["n"] == 1:
            payload = {"choices": [{"message": {
                "role": "assistant", "content": None,
                "tool_calls": [{
                    "id": "call_1", "type": "function",
                    "function": {"name": "search_saved_events", "arguments": json.dumps({"days_ahead": 60})},
                }],
            }}]}
        else:
            payload = {"choices": [{"message": {"role": "assistant", "content": "You have the Albany MWBE Forum coming up."}}]}
        return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    res = client.post("/ask", json={"question": "What's coming up?"})

    body = res.json()
    assert body["mode"] == "ai"
    assert "Albany MWBE Forum" in body["answer"]
    assert len(body["events"]) == 1
    assert calls["n"] == 2
