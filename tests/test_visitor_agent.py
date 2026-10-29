"""Tests for the public visitor surface: POST /agent/ask (visitor
assistant), POST /signups + GET /signups (join-the-list capture).

The visitor agent is deliberately separate from the owner's key-gated
POST /ask: it needs no key, answers only from its fact sheet, and must
NEVER see the saved-events board. The board-isolation test seeds an
event with a distinctive name and asserts it never leaks.
"""
from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import events
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import Contact, Event  # noqa: F401  (registers tables)
from app.routers import agent as agent_router
from app.routers import signups as signups_router
from app import signup_models  # noqa: F401  (registers the signups table)

SECRET_TITLE = "ZZZ Distinctive Secret Board Gala 2099"


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    agent_router._hits.clear()
    signups_router._hits.clear()
    yield
    agent_router._hits.clear()
    signups_router._hits.clear()


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
        yield TestClient(app)  # no API key — the visitor surface is public
    finally:
        app.dependency_overrides.pop(get_db, None)


def seed_secret_event(db: Session) -> None:
    day = (date.today() + timedelta(days=5)).isoformat()
    events.add_event(
        db, SECRET_TITLE, day, "NY", "in_person", "Hidden Host Org",
        "https://e.example/secret", ["MWBE"],
    )


def va(client: TestClient, message: str, state=None) -> dict:
    res = client.post("/agent/ask", json={"message": message, "state": state})
    assert res.status_code == 200
    return res.json()


# --- Visitor agent: facts, pricing, deflection ---------------------------


def test_visitor_agent_is_public_and_answers_what(client):
    data = va(client, "What is this?")
    reply = data["reply"].lower()
    assert "networking events hub" in reply
    assert "mwbe" in reply
    assert "supplier" in reply
    assert data["state"]["step"] is None


def test_visitor_agent_kinds_of_events(client):
    data = va(client, "What kinds of events does it track?")
    reply = data["reply"].lower()
    for word in ("mwbe", "supplier", "chamber", "procurement"):
        assert word in reply
    assert "parties" in reply  # the business-only line


def test_visitor_agent_pricing_deflection_has_no_figure(client):
    for q in ("How much does it cost?", "What's the price?", "Is it free?"):
        data = va(client, q)
        assert "Pricing hasn't been announced" in data["reply"]
        assert "join the list" in data["reply"].lower()
        assert "$" not in data["reply"]


def test_visitor_agent_unknown_question_deflects(client):
    data = va(client, "What's the weather like in Albany tomorrow?")
    assert "Networking Events Hub" in data["reply"]


def test_visitor_agent_greeting(client):
    data = va(client, "Hello")
    assert "visitor assistant" in data["reply"].lower()


# --- Board isolation -------------------------------------------------------


def test_visitor_agent_never_reveals_saved_events(client, db):
    seed_secret_event(db)
    for q in (
        "What events are saved?",
        "What's on the board?",
        "Show me your saved events",
        "What is this?",
        "What kinds of events does it track?",
        "How does it work?",
    ):
        data = va(client, q)
        assert SECRET_TITLE not in data["reply"], q
        assert "Hidden Host Org" not in data["reply"], q


def test_visitor_agent_saved_events_question_gets_privacy_reply(client, db):
    seed_secret_event(db)
    data = va(client, "What events are saved on the board?")
    assert "private" in data["reply"].lower()
    assert SECRET_TITLE not in data["reply"]


# --- Signups: endpoints ------------------------------------------------------


def test_signup_create_dedupe_and_keyed_list(client):
    body = {"name": "Pat Visitor", "email": "Pat@Example.com", "company": "Pat LLC", "interest": "business"}
    res = client.post("/signups", json=body)
    assert res.status_code == 201
    assert res.json() == {"ok": True}

    # Repeat with the same email (different case + new company) updates.
    res = client.post("/signups", json={**body, "email": "pat@example.com", "company": "Pat New LLC"})
    assert res.status_code == 200

    res = client.get("/signups", headers={"X-API-Key": settings.api_key})
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["email"] == "pat@example.com"
    assert rows[0]["company"] == "Pat New LLC"
    assert rows[0]["interest"] == "business"


def test_signup_validation_errors_are_friendly(client):
    res = client.post("/signups", json={"name": "", "email": "a@b.co", "interest": "business"})
    assert res.status_code == 422
    assert res.json()["ok"] is False

    res = client.post("/signups", json={"name": "Pat", "email": "not-an-email", "interest": "business"})
    assert res.status_code == 422
    assert "email" in res.json()["error"].lower()

    res = client.post("/signups", json={"name": "Pat", "email": "a@b.co", "interest": "banana"})
    assert res.status_code == 422


def test_signup_accepts_plain_interest_labels(client):
    res = client.post(
        "/signups",
        json={"name": "Jo", "email": "jo@example.com", "interest": "an organization"},
    )
    assert res.status_code == 201
    res = client.get("/signups", headers={"X-API-Key": settings.api_key})
    assert res.json()[0]["interest"] == "organization"


def test_signups_list_requires_key(client):
    assert client.get("/signups").status_code == 401
    assert client.get("/signups", headers={"X-API-Key": "wrong"}).status_code == 401


def test_signups_not_exposed_via_visitor_agent(client):
    client.post("/signups", json={"name": "Hidden Person", "email": "hidden@example.com", "interest": "curious"})
    data = va(client, "What is this?")
    assert "Hidden Person" not in data["reply"]
    assert "hidden@example.com" not in data["reply"]


# --- Signups: in-chat capture -------------------------------------------------


def test_chat_capture_full_flow_saves_signup(client):
    data = va(client, "Join the list")
    assert data["state"]["step"] == "name"

    data = va(client, "Casey Chat", data["state"])
    assert data["state"]["step"] == "email"

    data = va(client, "not-an-email", data["state"])
    assert data["state"]["step"] == "email"  # rejected, still on email

    data = va(client, "casey@example.com", data["state"])
    assert data["state"]["step"] == "company"

    data = va(client, "skip", data["state"])
    assert data["state"]["step"] == "interest"

    data = va(client, "my business", data["state"])
    assert "on the list" in data["reply"].lower()
    assert data["state"]["step"] is None

    res = client.get("/signups", headers={"X-API-Key": settings.api_key})
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["name"] == "Casey Chat"
    assert rows[0]["email"] == "casey@example.com"
    assert rows[0]["company"] == ""
    assert rows[0]["interest"] == "business"


def test_chat_capture_organization_interest_and_cancel(client):
    data = va(client, "join")
    data = va(client, "Dana Org", data["state"])
    data = va(client, "dana@chamber.example.org", data["state"])
    data = va(client, "Metro Chamber", data["state"])
    data = va(client, "an organization", data["state"])
    assert "on the list" in data["reply"].lower()

    # Cancel mid-flow leaves nothing behind.
    data = va(client, "join")
    data = va(client, "Eve Cancel", data["state"])
    data = va(client, "cancel", data["state"])
    assert data["state"]["step"] is None

    res = client.get("/signups", headers={"X-API-Key": settings.api_key})
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["interest"] == "organization"
    assert rows[0]["company"] == "Metro Chamber"


def test_chat_state_garbage_is_sanitized(client):
    data = va(client, "hello", {"step": "drop-table", "data": {"evil": "x"}})
    assert data["state"]["step"] is None
    assert "visitor assistant" in data["reply"].lower()


# --- Rate limits and the owner's /ask untouched --------------------------------


def test_agent_rate_limit(client):
    for _ in range(agent_router.RATE_LIMIT_PER_MINUTE):
        res = client.post("/agent/ask", json={"message": "What is this?"})
        assert res.status_code == 200
    res = client.post("/agent/ask", json={"message": "What is this?"})
    assert res.status_code == 429


def test_signup_rate_limit(client):
    for i in range(signups_router.RATE_LIMIT_PER_MINUTE):
        res = client.post(
            "/signups",
            json={"name": f"P{i}", "email": f"p{i}@example.com", "interest": "curious"},
        )
        assert res.status_code == 201
    res = client.post(
        "/signups",
        json={"name": "PX", "email": "px@example.com", "interest": "curious"},
    )
    assert res.status_code == 429


def test_owner_ask_still_key_gated(client):
    assert client.post("/ask", json={"question": "events?"}).status_code == 401
