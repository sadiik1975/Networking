"""Shared constants and pure helpers: compatibility scoring and follow-up drafts."""
import re

from app.brands import BRAND_KEYS, get_brands

DEFAULT_STATES = ["NY", "NJ", "CT", "MA"]
SUPPORTED_STATES = [*DEFAULT_STATES, "PA", "DE", "DC"]
TARGET_GROUPS = {
    "B2B_Networking", "Small_Business", "Startup_Tech", "Chamber_of_Commerce",
    "WMBE", "MWBE", "Muslim_Business", "Supplier_Diversity", "Tech_Contracting",
    "Nightlife", "Hip_Hop", "R_and_B", "Latin", "Afrobeats", "Live_Music",
    "Lounges", "Concerts", "Parties",
}
EVENT_FORMATS = {"in_person", "virtual", "hybrid", "all"}
PROSPECT_TYPES = {"potential_client", "partner", "investor", "prime_contractor", "networking_host"}
CAPTURE_TYPES = {"business_card_image", "audio_voice_note", "live_convo_summary", "manual"}

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")


def resolve_brand(brand: str) -> dict | None:
    return get_brands().get((brand or "").strip().lower())


def extract_contact_fields(text: str) -> dict:
    email = _EMAIL.search(text)
    phone = _PHONE.search(text)
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    return {
        "name": first_line if len(first_line) <= 60 and not _EMAIL.search(first_line) else None,
        "email": email.group(0) if email else None,
        "phone": phone.group(0) if phone else None,
    }


def score_compatibility(
    brand: str,
    prospect_name: str,
    industry: str,
    prospect_type: str = "potential_client",
    certified_wmbe_or_mbe: bool = False,
    community_affiliated: bool = False,
    perceived_needs: list[str] | None = None,
) -> dict:
    brand_info = resolve_brand(brand)
    if brand_info is None:
        return {"error": f"brand must be one of {list(BRAND_KEYS)}"}
    if prospect_type not in PROSPECT_TYPES:
        return {"error": f"prospect_type must be one of {sorted(PROSPECT_TYPES)}"}
    needs = perceived_needs or []

    # Transparent heuristic: each factor is capped and the total is out of 10.
    hits = sum(any(k in need.lower() for k in brand_info["keywords"]) for need in needs)
    need_fit = min(4.0, hits * 1.5)
    role_fit = {
        "potential_client": 2.5, "partner": 2.5, "investor": 2.0,
        "prime_contractor": 2.0, "networking_host": 1.5,
    }[prospect_type]
    cert_fit = 3.0 if certified_wmbe_or_mbe else 1.0
    community_fit = 1.0 if community_affiliated else 0.0
    score = round(min(10.0, need_fit + role_fit + cert_fit + community_fit), 1)

    return {
        "brand": brand_info["name"],
        "prospect": prospect_name,
        "industry": industry,
        "prospect_type": prospect_type,
        "compatibility_score": score,
        "match_breakdown": {
            "need_fit": f"{need_fit}/4",
            "role_fit": f"{role_fit}/2.5",
            "certification_fit": f"{cert_fit}/3",
            "community_fit": f"{community_fit}/1",
        },
        "website": brand_info["url"],
        "basis": "Heuristic from the inputs provided; unknown fields default to not-certified / no stated needs.",
    }


def draft_followup(
    brand: str,
    contact_name: str,
    offering_focus: str,
    contact_email: str | None = None,
    highlights: list[str] | None = None,
    event_context: str = "",
) -> dict:
    brand_info = resolve_brand(brand)
    if brand_info is None:
        return {"error": f"brand must be one of {list(BRAND_KEYS)}"}
    offerings = brand_info["offerings"]
    if offering_focus not in offerings:
        return {"error": f"offering_focus for {brand} must be one of {sorted(offerings)}"}

    where = f" at {event_context}" if event_context else ""
    bullets = "\n".join(f"- {h}" for h in (highlights or []))
    body = (
        f"Hi {contact_name},\n\n"
        f"It was great connecting{where}. {brand_info['name']} is {brand_info['pitch']}, "
        f"focused on {offerings[offering_focus]}."
        + (f" Based on our conversation, here is where we can help:\n{bullets}\n" if bullets else "\n")
        + f"\nWould you be open to a 20-minute call this week? More about us: {brand_info['url']}\n\n"
        f"Best regards,\n{brand_info['name']}"
    )
    return {
        "to": contact_email,
        "subject": f"Great meeting you, {contact_name}",
        "body": body,
        "status": "draft_not_sent",
    }
