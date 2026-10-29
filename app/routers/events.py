from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import event_discovery, events, networking, telegram_reports
from app.auth import require_api_key
from app.config import settings
from app.database import get_db
from app.schemas import (
    CompatibilityRequest,
    ContactCreate,
    ContactUpdate,
    EventCreate,
    EventUpdate,
    FollowupRequest,
    HealthResponse,
    ReminderRequest,
)

router = APIRouter()
protected = APIRouter(dependencies=[Depends(require_api_key)])


def _ok(result: dict, not_found: str | None = None) -> dict:
    """Turn the service layer's {"error": ...} results into HTTP errors."""
    if "error" in result:
        code = 404 if not_found and result["error"] == not_found else 400
        raise HTTPException(status_code=code, detail=result["error"])
    return result


@router.get("/health", response_model=HealthResponse, tags=["health"], summary="Service and database health check")
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "unavailable"
    return HealthResponse(status="ok", database=db_status, version=settings.app_version)


@protected.get("/events", tags=["events"], summary="Search saved business networking events")
def search_events(
    states: list[str] | None = Query(None),
    target_groups: list[str] | None = Query(None),
    event_format: str = "all",
    days_ahead: int = Query(60, ge=1, le=365),
    status: list[str] | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    return _ok(events.search_events(db, states, target_groups, event_format, days_ahead, status))


@protected.get("/events/discover", tags=["events"], summary="Web-search for unverified business networking event candidates")
def discover_events(
    states: list[str] | None = Query(None),
    target_groups: list[str] | None = Query(None),
    event_format: str = "all",
    max_results: int = Query(10, ge=1, le=20),
) -> dict:
    return _ok(event_discovery.discover_candidates(states, target_groups, event_format, max_results))


@protected.post("/events", status_code=201, tags=["events"], summary="Save a verified business networking event")
def create_event(body: EventCreate, db: Session = Depends(get_db)) -> dict:
    return _ok(events.add_event(
        db, body.title, body.event_date.isoformat(), body.state, body.event_format, body.organizer,
        str(body.registration_url), body.target_groups, body.location, body.time, body.status,
        body.brand, body.notes,
    ))


@protected.patch("/events/{event_id}", tags=["events"], summary="Update status, brand or notes")
def update_event(event_id: str, body: EventUpdate, db: Session = Depends(get_db)) -> dict:
    return _ok(events.update_event(db, event_id, body.status, body.notes, body.brand), "Event not found")


@protected.post("/contacts", status_code=201, tags=["contacts"], summary="Save a contact or event capture")
def create_contact(body: ContactCreate, db: Session = Depends(get_db)) -> dict:
    return _ok(events.save_contact(db, **body.model_dump()))


@protected.get("/contacts", tags=["contacts"], summary="List contacts")
def list_contacts(
    followup_status: str | None = None,
    event_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    return _ok(events.list_contacts(db, followup_status, event_id, limit))


@protected.patch("/contacts/{contact_id}", tags=["contacts"], summary="Update a contact")
def update_contact(contact_id: str, body: ContactUpdate, db: Session = Depends(get_db)) -> dict:
    return _ok(events.update_contact(db, contact_id, **body.model_dump(exclude_unset=True)), "Contact not found")


@protected.post("/contacts/{contact_id}/followup", tags=["contacts"], summary="Draft a follow-up email (never sent)")
def draft_followup(contact_id: str, body: FollowupRequest, db: Session = Depends(get_db)) -> dict:
    return _ok(events.followup_for_contact(db, contact_id, body.brand, body.offering_focus, body.highlights), "Contact not found")


@protected.post("/compatibility", tags=["matching"], summary="Score a prospect against Borough Build or Been Ventures")
def compatibility(body: CompatibilityRequest) -> dict:
    return _ok(networking.score_compatibility(**body.model_dump()))


@protected.post("/reminders/telegram", tags=["reminders"], summary="Send upcoming business networking reminders to Telegram")
def send_reminders(body: ReminderRequest, db: Session = Depends(get_db)) -> dict:
    digest = events.reminder_digest(db, body.days_ahead)
    if digest.get("count", 0) == 0:
        return digest
    result = telegram_reports.send_report(digest["text"], body.confirmed)
    return _ok(result) | {"events": digest["count"]}


router.include_router(protected)
