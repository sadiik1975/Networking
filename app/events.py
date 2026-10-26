"""Database-backed events and contacts. Nothing here invents events or sends messages."""
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app import networking
from app.models import EVENT_STATUSES, FOLLOWUP_STATUSES, Contact, Event

CURATED_FILE = Path(__file__).resolve().parent.parent / "data" / "networking_events.json"


def event_to_dict(event: Event) -> dict:
    return {
        "event_id": event.id,
        "title": event.title,
        "date": event.date,
        "time": event.time,
        "state": event.state,
        "location": event.location,
        "format": event.format,
        "organizer": event.organizer,
        "target_groups": event.target_groups,
        "registration_url": event.registration_url,
        "status": event.status,
        "brand": event.brand,
        "notes": event.notes,
    }


def contact_to_dict(contact: Contact) -> dict:
    return {
        "contact_id": contact.id,
        "name": contact.name,
        "company": contact.company,
        "email": contact.email,
        "phone": contact.phone,
        "event_id": contact.event_id,
        "event_context": contact.event_context,
        "capture_type": contact.capture_type,
        "notes": contact.notes,
        "brand": contact.brand,
        "followup_status": contact.followup_status,
        "created_at": contact.created_at.isoformat(),
    }


def add_event(
    db: Session,
    title: str,
    event_date: str,
    state: str,
    event_format: str,
    organizer: str,
    registration_url: str,
    target_groups: list[str] | None = None,
    location: str = "",
    time: str = "",
    status: str = "interested",
    brand: str | None = None,
    notes: str = "",
) -> dict:
    try:
        parsed = date.fromisoformat(event_date)
    except ValueError:
        return {"error": "event_date must be YYYY-MM-DD"}
    if state.upper() not in networking.SUPPORTED_STATES:
        return {"error": f"state must be within {networking.SUPPORTED_STATES}"}
    if event_format not in networking.EVENT_FORMATS - {"all"}:
        return {"error": "event_format must be in_person, virtual, or hybrid"}
    groups = target_groups or []
    if not set(groups) <= networking.TARGET_GROUPS:
        return {"error": f"target_groups must be within {sorted(networking.TARGET_GROUPS)}"}
    if not registration_url.startswith(("http://", "https://")):
        return {"error": "registration_url must be an http(s) URL"}
    if not title.strip() or not organizer.strip():
        return {"error": "title and organizer are required"}
    if status not in EVENT_STATUSES:
        return {"error": f"status must be one of {list(EVENT_STATUSES)}"}
    if brand and networking.resolve_brand(brand) is None:
        return {"error": "brand must be borough_build or been_ventures"}

    duplicate = db.query(Event).filter(Event.registration_url == registration_url, Event.date == event_date).first()
    if duplicate:
        return {"error": "Event already exists", "event_id": duplicate.id}

    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:40]
    event = Event(
        id=f"evt_{parsed.isoformat()}_{slug}_{uuid4().hex[:4]}",
        title=title.strip(), date=event_date, time=time, state=state.upper(), location=location,
        format=event_format, organizer=organizer.strip(), target_groups=groups,
        registration_url=registration_url, status=status, brand=brand, notes=notes,
    )
    db.add(event)
    db.commit()
    return {"saved": event_to_dict(event)}


def search_events(
    db: Session,
    states: list[str] | None = None,
    target_groups: list[str] | None = None,
    event_format: str = "all",
    days_ahead: int = 60,
    statuses: list[str] | None = None,
) -> dict:
    states_up = {s.upper() for s in (states or networking.DEFAULT_STATES)}
    groups = set(target_groups or [])
    if not states_up <= set(networking.SUPPORTED_STATES):
        return {"error": f"states must be within {networking.SUPPORTED_STATES}"}
    if not groups <= networking.TARGET_GROUPS:
        return {"error": f"target_groups must be within {sorted(networking.TARGET_GROUPS)}"}
    if event_format not in networking.EVENT_FORMATS:
        return {"error": f"event_format must be one of {sorted(networking.EVENT_FORMATS)}"}
    if statuses and not set(statuses) <= set(EVENT_STATUSES):
        return {"error": f"statuses must be within {list(EVENT_STATUSES)}"}

    today = date.today()
    query = db.query(Event).filter(
        Event.date >= today.isoformat(),
        Event.date <= (today + timedelta(days=days_ahead)).isoformat(),
        Event.state.in_(states_up),
    )
    if statuses:
        query = query.filter(Event.status.in_(statuses))
    if event_format != "all":
        query = query.filter(Event.format == event_format)

    results = [
        e for e in query.order_by(Event.date, Event.time).all()
        if not groups or groups & set(e.target_groups)
    ]
    note = None if results else "No saved events matched. Use discovery to find candidates, then confirm the ones you want."
    return {"source": "saved_events", "count": len(results), "events": [event_to_dict(e) for e in results], "note": note}


def update_event(db: Session, event_id: str, status: str | None = None, notes: str | None = None, brand: str | None = None) -> dict:
    event = db.get(Event, event_id)
    if event is None:
        return {"error": "Event not found"}
    if status is not None:
        if status not in EVENT_STATUSES:
            return {"error": f"status must be one of {list(EVENT_STATUSES)}"}
        event.status = status
    if brand is not None:
        if brand and networking.resolve_brand(brand) is None:
            return {"error": "brand must be borough_build or been_ventures"}
        event.brand = brand or None
    if notes is not None:
        event.notes = notes
    db.commit()
    return {"saved": event_to_dict(event)}


def reminder_digest(db: Session, days_ahead: int = 7) -> dict:
    """Text summary of interested/registered events happening soon."""
    found = search_events(db, days_ahead=days_ahead, statuses=["interested", "registered"])
    if found.get("error"):
        return found
    if not found["events"]:
        return {"count": 0, "text": f"No saved events in the next {days_ahead} days."}
    lines = [f"Upcoming nightlife events (next {days_ahead} days):"]
    for e in found["events"]:
        when = f"{e['date']} {e['time']}".strip()
        place = e["location"] or e["format"].replace("_", " ")
        lines.append(f"\n{when} - {e['title']} [{e['status']}]\n{place} ({e['state']})\n{e['registration_url']}")
    return {"count": len(found["events"]), "text": "\n".join(lines)}


def import_curated_file_if_empty(db: Session) -> int:
    if db.query(Event).count() or not CURATED_FILE.exists():
        return 0
    imported = 0
    for item in json.loads(CURATED_FILE.read_text(encoding="utf-8")):
        result = add_event(
            db, item.get("title", ""), item.get("date", ""), item.get("state", ""), item.get("format", ""),
            item.get("organizer", ""), item.get("registration_url", ""), item.get("target_groups"),
            item.get("location", ""), item.get("time", ""), status="discovered",
        )
        imported += "saved" in result
    return imported


def save_contact(
    db: Session,
    capture_type: str,
    raw_text: str,
    event_context: str = "",
    event_id: str | None = None,
    name: str | None = None,
    company: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    notes: str = "",
    brand: str | None = None,
) -> dict:
    if capture_type not in networking.CAPTURE_TYPES:
        return {"error": f"capture_type must be one of {sorted(networking.CAPTURE_TYPES)}"}
    text = (raw_text or "").strip()
    if not text and not (name or email):
        return {"error": "Provide raw text, or at least a name or email"}
    if brand and networking.resolve_brand(brand) is None:
        return {"error": "brand must be borough_build or been_ventures"}
    if event_id and db.get(Event, event_id) is None:
        return {"error": "Event not found"}

    guessed = networking.extract_contact_fields(text) if text else {}
    contact = Contact(
        id=f"CON-{uuid4().hex[:10].upper()}",
        name=name or (guessed.get("name") if capture_type == "business_card_image" else None),
        company=company,
        email=email or guessed.get("email"),
        phone=phone or guessed.get("phone"),
        event_id=event_id, event_context=event_context, capture_type=capture_type,
        raw_text=text, notes=notes, brand=brand,
    )
    db.add(contact)
    db.commit()
    result = contact_to_dict(contact)
    result["note"] = "Extracted fields are best-effort; verify before follow-up."
    return result


def list_contacts(db: Session, followup_status: str | None = None, event_id: str | None = None, limit: int = 50) -> dict:
    if followup_status and followup_status not in FOLLOWUP_STATUSES:
        return {"error": f"followup_status must be one of {list(FOLLOWUP_STATUSES)}"}
    query = db.query(Contact)
    if followup_status:
        query = query.filter(Contact.followup_status == followup_status)
    if event_id:
        query = query.filter(Contact.event_id == event_id)
    rows = query.order_by(Contact.created_at.desc()).limit(max(1, min(limit, 200))).all()
    return {"count": len(rows), "contacts": [contact_to_dict(c) for c in rows]}


def update_contact(db: Session, contact_id: str, **fields) -> dict:
    contact = db.get(Contact, contact_id)
    if contact is None:
        return {"error": "Contact not found"}
    status = fields.get("followup_status")
    if status is not None and status not in FOLLOWUP_STATUSES:
        return {"error": f"followup_status must be one of {list(FOLLOWUP_STATUSES)}"}
    if fields.get("brand") and networking.resolve_brand(fields["brand"]) is None:
        return {"error": "brand must be borough_build or been_ventures"}
    for key in ("name", "company", "email", "phone", "notes", "brand", "followup_status"):
        if fields.get(key) is not None:
            setattr(contact, key, fields[key])
    db.commit()
    return {"saved": contact_to_dict(contact)}


def followup_for_contact(db: Session, contact_id: str, brand: str, offering_focus: str, highlights: list[str] | None = None) -> dict:
    contact = db.get(Contact, contact_id)
    if contact is None:
        return {"error": "Contact not found"}
    draft = networking.draft_followup(
        brand, contact.name or "there", offering_focus, contact.email, highlights, contact.event_context,
    )
    if "error" not in draft:
        contact.brand = brand
        if contact.followup_status == "new":
            contact.followup_status = "drafted"
        db.commit()
    return draft
