from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import events, telegram_bot
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import Event  # noqa: F401  (registers tables)

CHAT_ID = "424242"


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
        # No X-API-Key header on purpose: the webhook must not require one.
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def sent(client, monkeypatch) -> list:
    replies: list = []
    monkeypatch.setattr(settings, "telegram_chat_id", CHAT_ID)
    monkeypatch.setattr(settings, "telegram_webhook_secret", None)
    monkeypatch.setattr(
        telegram_bot, "send_reply",
        lambda chat_id, text: replies.append((chat_id, text)) or {"status": "sent"},
    )
    return replies


def soon(days: int = 5) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def add(db: Session, title="NYC B2B Mixer", day=5, **kw):
    kw.setdefault("target_groups", ["B2B_Networking"])
    return events.add_event(
        db, title, soon(day), "NY", "in_person", "Host Org",
        kw.pop("url", f"https://e.example/{title.replace(' ', '-')}"), **kw,
    )


def update(text: str, chat_id: str = CHAT_ID) -> dict:
    return {
        "update_id": 1,
        "message": {"message_id": 1, "chat": {"id": int(chat_id), "type": "private"}, "text": text},
    }


def test_webhook_ignores_other_chats(client, sent):
    response = client.post("/telegram/webhook", json=update("events", chat_id="999999"))
    assert response.status_code == 200
    assert sent == []


def test_webhook_events_command_replies_with_saved_event(client, db, sent):
    add(db)
    response = client.post("/telegram/webhook", json=update("events"))
    assert response.status_code == 200
    assert len(sent) == 1
    assert sent[0][0] == CHAT_ID
    assert "NYC B2B Mixer" in sent[0][1]


def test_webhook_week_command_only_covers_next_7_days(client, db, sent):
    add(db, "This Week", day=3, url="https://e.example/week")
    add(db, "Next Month", day=30, url="https://e.example/month")
    client.post("/telegram/webhook", json=update("/week"))
    assert "This Week" in sent[0][1]
    assert "Next Month" not in sent[0][1]


def test_webhook_mwbe_command_filters_target_groups(client, db, sent):
    add(db, "MWBE Expo", target_groups=["MWBE"], url="https://e.example/mwbe")
    add(db, "Tech Night", target_groups=["Startup_Tech"], url="https://e.example/tech")
    client.post("/telegram/webhook", json=update("wmbe"))
    assert "MWBE Expo" in sent[0][1]
    assert "Tech Night" not in sent[0][1]


def test_webhook_unknown_text_returns_help(client, sent):
    client.post("/telegram/webhook", json=update("surprise me"))
    assert len(sent) == 1
    assert "events" in sent[0][1] and "week" in sent[0][1] and "mwbe" in sent[0][1]


def test_webhook_secret_enforced_when_configured(client, sent, monkeypatch):
    monkeypatch.setattr(settings, "telegram_webhook_secret", "test-secret")
    assert client.post("/telegram/webhook", json=update("events")).status_code == 403
    assert sent == []
    ok = client.post(
        "/telegram/webhook", json=update("events"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert ok.status_code == 200
    assert len(sent) == 1
