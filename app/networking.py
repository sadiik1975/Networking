"""Networking-event intelligence for Borough Build, exposed via app.mcp_server.

Events come from a curated JSON file (data/networking_events.json) that the
owner maintains; nothing here invents or scrapes events. Captures from Muse /
smart glasses are stored in SQLite. Follow-ups are drafts only and are never sent.
"""
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

AGENCY_URL = "https://boroughbuild.netlify.app/"
DEFAULT_STATES = ["NY", "NJ", "CT", "MA", "PA", "DE", "DC"]
EVENTS_FILE = Path(__file__).resolve().parent.parent / "data" / "networking_events.json"

TARGET_GROUPS = {"WMBE", "MWBE", "Muslim_Business", "Supplier_Diversity", "Tech_Contracting"}
EVENT_FORMATS = {"in_person", "virtual", "hybrid", "all"}
PROSPECT_TYPES = {"potential_client", "subcontractor_partner", "prime_contractor", "networking_host"}
OFFERINGS = {
    "web_design": "web application development and UI design",
    "ai_agent_integration": "custom AI agent integrations and automations",
    "full_digital_agency": "web development, AI automation, branding and digital strategy",
}

TECH_KEYWORDS = ("website", "web", "app", "ai", "automation", "digital", "brand", "software", "seo", "modern")


class NetworkingCapture(Base):
    __tablename__ = "networking_captures"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    capture_type: Mapped[str] = mapped_column(String)
    event_context: Mapped[str] = mapped_column(String, default="")
    raw_text: Mapped[str] = mapped_column(Text)
    contact_name: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String, nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def _load_events() -> list[dict]:
    if not EVENTS_FILE.exists():
        return []
    return json.loads(EVENTS_FILE.read_text(encoding="utf-8"))


def search_events(
    states: list[str],
    target_groups: list[str],
    event_format: str = "all",
    days_ahead: int = 60,
) -> dict:
    states_up = {s.upper() for s in states}
    groups = set(target_groups)
    if not states_up <= set(DEFAULT_STATES):
        return {"error": f"states must be within {DEFAULT_STATES}"}
    if not groups <= TARGET_GROUPS:
        return {"error": f"target_groups must be within {sorted(TARGET_GROUPS)}"}
    if event_format not in EVENT_FORMATS:
        return {"error": f"event_format must be one of {sorted(EVENT_FORMATS)}"}

    today = date.today()
    horizon = today + timedelta(days=days_ahead)
    results = []
    for event in _load_events():
        try:
            event_date = date.fromisoformat(event["date"])
        except (KeyError, ValueError):
            continue
        if not today <= event_date <= horizon:
            continue
        if event.get("state", "").upper() not in states_up:
            continue
        if event_format != "all" and event.get("format") != event_format:
            continue
        if not groups & set(event.get("target_groups", [])):
            continue
        results.append(event)

    results.sort(key=lambda e: e["date"])
    note = None
    if not results:
        note = f"No curated events matched. Add verified events to {EVENTS_FILE.name} (see data/README.md)."
    return {"source": "curated_events_file", "count": len(results), "events": results, "note": note}


def score_compatibility(
    prospect_name: str,
    industry: str,
    prospect_type: str = "potential_client",
    wmbe_or_mbe_certified: bool = False,
    muslim_owned_or_affiliated: bool = False,
    perceived_tech_needs: list[str] | None = None,
) -> dict:
    if prospect_type not in PROSPECT_TYPES:
        return {"error": f"prospect_type must be one of {sorted(PROSPECT_TYPES)}"}
    needs = perceived_tech_needs or []

    # Transparent heuristic: each factor is capped and the total is out of 10.
    needs_hits = sum(any(k in need.lower() for k in TECH_KEYWORDS) for need in needs)
    tech_fit = min(4.0, needs_hits * 1.5)
    if prospect_type in {"prime_contractor", "subcontractor_partner"}:
        cert_fit = 3.0 if wmbe_or_mbe_certified else 1.5
        role_fit = 2.0
    elif prospect_type == "networking_host":
        cert_fit = 2.0 if wmbe_or_mbe_certified else 1.0
        role_fit = 1.5
    else:
        cert_fit = 1.5 if wmbe_or_mbe_certified else 1.0
        role_fit = 2.5
    community_fit = 1.0 if muslim_owned_or_affiliated else 0.0
    score = round(min(10.0, tech_fit + cert_fit + role_fit + community_fit), 1)

    return {
        "prospect": prospect_name,
        "industry": industry,
        "prospect_type": prospect_type,
        "compatibility_score": score,
        "match_breakdown": {
            "tech_need_fit": f"{tech_fit}/4",
            "certification_fit": f"{cert_fit}/3",
            "role_fit": f"{role_fit}/2.5",
            "community_fit": f"{community_fit}/1",
        },
        "agency_url": AGENCY_URL,
        "basis": "Heuristic from the inputs provided; unknown fields default to not-certified / no stated needs.",
    }


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")


def save_capture(db, capture_type: str, raw_text_or_transcript: str, event_context: str = "") -> dict:
    if capture_type not in {"business_card_image", "audio_voice_note", "live_convo_summary"}:
        return {"error": "capture_type must be business_card_image, audio_voice_note, or live_convo_summary"}
    text = raw_text_or_transcript.strip()
    if not text:
        return {"error": "raw_text_or_transcript is empty"}

    email = _EMAIL.search(text)
    phone = _PHONE.search(text)
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    name = first_line if capture_type == "business_card_image" and len(first_line) <= 60 else None

    capture = NetworkingCapture(
        id=f"CAP-{uuid4().hex[:10].upper()}",
        capture_type=capture_type,
        event_context=event_context,
        raw_text=text,
        contact_name=name,
        contact_email=email.group(0) if email else None,
        contact_phone=phone.group(0) if phone else None,
    )
    db.add(capture)
    db.commit()
    return {
        "id": capture.id,
        "contact_name": capture.contact_name,
        "contact_email": capture.contact_email,
        "contact_phone": capture.contact_phone,
        "event_context": event_context,
        "note": "Extracted fields are best-effort; verify before follow-up.",
    }


def draft_followup(
    lead_name: str,
    offering_focus: str,
    lead_email: str | None = None,
    compatibility_highlights: list[str] | None = None,
) -> dict:
    if offering_focus not in OFFERINGS:
        return {"error": f"offering_focus must be one of {sorted(OFFERINGS)}"}
    highlights = compatibility_highlights or []
    bullets = "\n".join(f"- {h}" for h in highlights)
    body = (
        f"Hi {lead_name},\n\n"
        f"It was great connecting. Borough Build is a minority-owned digital agency specializing in "
        f"{OFFERINGS[offering_focus]}."
        + (f" Based on our conversation, here is where we can help:\n{bullets}\n" if bullets else "\n")
        + f"\nWould you be open to a 20-minute call this week? More about our work: {AGENCY_URL}\n\n"
        "Best regards,\nBorough Build"
    )
    return {
        "to": lead_email,
        "subject": f"Great meeting you, {lead_name}: ideas from Borough Build",
        "body": body,
        "status": "draft_not_sent",
    }
