from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import events, networking, telegram_reports
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


def soon(days: int = 5) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def add(db: Session, title="NYC B2B Mixer", day=5, **kw):
    kw.setdefault("target_groups", ["B2B_Networking"])
    return events.add_event(
        db, title, soon(day), kw.pop("state", "NY"), "in_person", "Host Org",
        kw.pop("url", f"https://e.example/{title.replace(' ', '-')}"), **kw,
    )


def test_add_and_search_event(db):
    assert "saved" in add(db)
    result = events.search_events(db, ["NY"], ["B2B_Networking"])
    assert result["count"] == 1 and result["events"][0]["title"] == "NYC B2B Mixer"
    assert events.search_events(db, ["NJ"])["count"] == 0


def test_rejects_bad_input_and_duplicates(db):
    assert "error" in events.add_event(db, "x", "not-a-date", "NY", "in_person", "o", "https://e.example")
    assert "error" in events.add_event(db, "x", soon(), "TX", "in_person", "o", "https://e.example")
    assert "error" in events.add_event(db, "x", soon(), "NY", "in_person", "o", "ftp://e.example")
    assert "error" in add(db, brand="nope")
    add(db)
    assert add(db)["error"] == "Event already exists"


def test_past_and_far_events_are_excluded(db):
    add(db, "Past", day=-3, url="https://e.example/past")
    add(db, "Far", day=200, url="https://e.example/far")
    assert events.search_events(db, days_ahead=60)["count"] == 0


def test_update_status_and_reminder_digest(db):
    event_id = add(db)["saved"]["event_id"]
    assert events.reminder_digest(db, 7)["count"] == 1
    events.update_event(db, event_id, status="skipped")
    assert events.reminder_digest(db, 7)["count"] == 0
    assert "error" in events.update_event(db, event_id, status="bogus")
    assert events.update_event(db, "missing")["error"] == "Event not found"


def test_contact_capture_and_followup(db):
    saved = events.save_contact(
        db, "business_card_image", "Jane Doe\nAcme Co\njane@acme.com\n(212) 555-0199",
        "NYC B2B Mixer", brand="borough_build",
    )
    assert saved["name"] == "Jane Doe"
    assert saved["email"] == "jane@acme.com"
    assert saved["followup_status"] == "new"

    draft = events.followup_for_contact(db, saved["contact_id"], "borough_build", "web_design")
    assert draft["status"] == "draft_not_sent"
    assert "Borough Build" in draft["body"] and "NYC B2B Mixer" in draft["body"]
    assert events.list_contacts(db, "drafted")["count"] == 1


def test_followup_is_brand_specific(db):
    draft = networking.draft_followup("been_ventures", "Sam", "ai_tools")
    assert "Been Ventures" in draft["body"]
    assert "error" in networking.draft_followup("been_ventures", "Sam", "web_design")
    assert "error" in networking.draft_followup("unknown", "Sam", "web_design")


def test_compatibility_scoring_per_brand():
    result = networking.score_compatibility(
        "borough_build", "Acme", "Retail", "potential_client", True, True, ["new website", "AI automation"],
    )
    assert result["brand"] == "Borough Build" and result["compatibility_score"] == 9.5
    assert "error" in networking.score_compatibility("nope", "Acme", "Retail")


def test_rest_api_requires_key_and_round_trips(client):
    assert TestClient(app).get("/events").status_code == 401
    created = client.post("/events", json={
        "title": "AI Founders Meetup", "event_date": soon(), "state": "ny", "event_format": "in_person",
        "organizer": "NYC Tech", "registration_url": "https://e.example/ai", "target_groups": ["Startup_Tech"],
    })
    assert created.status_code == 201
    event_id = created.json()["saved"]["event_id"]
    assert client.patch(f"/events/{event_id}", json={"status": "registered"}).json()["saved"]["status"] == "registered"
    assert client.get("/events", params={"status": "registered"}).json()["count"] == 1
    assert client.post("/events", json={"title": "x"}).status_code == 422
    assert client.patch("/events/missing", json={"status": "attended"}).status_code == 404

    contact = client.post("/contacts", json={"capture_type": "live_convo_summary", "raw_text": "Met Sam, sam@x.io"})
    assert contact.status_code == 201
    cid = contact.json()["contact_id"]
    assert client.post(f"/contacts/{cid}/followup", json={"brand": "been_ventures", "offering_focus": "partnership"}).status_code == 200
    assert client.post("/contacts", json={"capture_type": "bogus", "raw_text": "x"}).status_code == 400


def test_telegram_reminder_requires_confirmation(client, db, monkeypatch):
    add(db)
    monkeypatch.setattr(settings, "telegram_bot_token", None)
    assert client.post("/reminders/telegram", json={}).status_code == 400
    sent = []
    monkeypatch.setattr(telegram_reports, "send_report", lambda text, confirmed: sent.append(text) or {"status": "sent"})
    assert client.post("/reminders/telegram", json={"confirmed": True}).json() == {"status": "sent", "events": 1}
    assert "NYC B2B Mixer" in sent[0]


def test_curated_file_import_only_when_empty(db, monkeypatch, tmp_path):
    import json
    file = tmp_path / "events.json"
    file.write_text(json.dumps([{
        "title": "Curated Expo", "date": soon(), "state": "NJ", "format": "hybrid",
        "organizer": "Org", "registration_url": "https://e.example/c", "target_groups": ["MWBE"],
    }]))
    monkeypatch.setattr(events, "CURATED_FILE", file)
    assert events.import_curated_file_if_empty(db) == 1
    assert events.import_curated_file_if_empty(db) == 0
