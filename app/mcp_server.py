"""MCP server exposing the lead search/detail logic as conversational tools.

Run with: `python -m app.mcp_server` (stdio transport) so an MCP-compatible
agent host (e.g. Muse, Claude Desktop) can query leads in plain language
instead of calling the REST endpoints directly. Shares the same SQLite-backed
data as the FastAPI app in `app.main`.
"""
from mcp.server.fastmcp import FastMCP

from uuid import uuid4

from app.company_models import CompanyProfile
from app.database import Base, SessionLocal, engine, migrate_schema
from app.dispatch_models import Contractor, Outreach, OutreachChannel, OutreachStatus
from app.geo import LocationNotFoundError, haversine_miles, resolve_location
from app.models_db import Trade
from app.seed import seed_dispatch_if_empty, seed_if_empty
from app import crud, event_discovery, networking, telegram_reports

from mcp.server.transport_security import TransportSecuritySettings

# Allow public hostnames when hosted; the default only accepts localhost Host headers.
mcp = FastMCP(
    "muse-contractor-leads",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

Base.metadata.create_all(bind=engine)
migrate_schema()
_db = SessionLocal()
seed_if_empty(_db)
seed_dispatch_if_empty(_db)


@mcp.tool()
def search_leads(
    trade: str,
    location: str | None = None,
    radius_miles: int = 100,
    min_value: float | None = None,
    zip_code: str | None = None,
    ownership_filter: str | None = None,
) -> list[dict]:
    """Search verified local project leads by trade and geographic radius.

    Args:
        trade: One of electrical, roofing, plumbing, hvac, general_contracting,
            flooring, landscaping, fencing, solar, remodeling.
        location: ZIP code or "City, ST" to search around.
        radius_miles: Search radius in miles.
        min_value: Optional minimum estimated project value.
        zip_code: Optional ZIP code alias for location.
        ownership_filter: Exact ownership category, such as Minority-Owned.
    """
    try:
        trade_enum = Trade(trade.lower())
    except ValueError:
        return [{"error": f"Unknown trade {trade!r}. Valid values: {[t.value for t in Trade]}"}]

    try:
        matches = crud.search_leads(
            db=_db,
            trade=trade_enum,
            location=zip_code or location or "",
            radius_miles=radius_miles,
            min_value=min_value,
            ownership_filter=ownership_filter,
            max_results=50,
        )
    except LocationNotFoundError as exc:
        return [{"error": str(exc)}]

    return [
        {
            "id": lead.id,
            "trade": lead.trade.value,
            "project_type": lead.project_type,
            "description": lead.description,
            "city": lead.city,
            "state": lead.state,
            "zip_code": lead.zip_code,
            "distance_miles": round(distance, 2),
            "estimated_value": lead.estimated_value,
            "issue_date": lead.issue_date.isoformat(),
            "project_scale": lead.project_scale.value,
            "municipal_source_url": lead.municipal_source_url,
            "ownership_category": lead.ownership_category,
            "certification_details": lead.certification_details,
            "source_url": lead.source_url,
        }
        for lead, distance in matches
    ]


@mcp.tool()
def search_hvac_businesses(location: str, radius_miles: float = 15, limit: int = 25) -> dict:
    """Find real HVAC businesses mapped in OpenStreetMap near a ZIP code or "City, ST".

    Coverage depends on OSM data and is not exhaustive; missing contact fields are null.
    """
    from app import overpass

    try:
        return overpass.search_hvac_businesses(location, radius_miles, limit)
    except (LocationNotFoundError, overpass.InvalidSearch, overpass.ProviderError) as exc:
        return {"error": str(exc), "source": "openstreetmap_overpass", "results": []}


@mcp.tool()
def get_lead(lead_id: str) -> dict:
    """Retrieve deep-dive dispatch details for a specific lead by its ID."""
    lead = crud.get_lead(_db, lead_id)
    if lead is None:
        return {"error": f"Lead {lead_id!r} not found"}

    return {
        "id": lead.id,
        "trade": lead.trade.value,
        "project_type": lead.project_type,
        "description": lead.description,
        "address_line1": lead.address_line1,
        "city": lead.city,
        "state": lead.state,
        "zip_code": lead.zip_code,
        "latitude": lead.latitude,
        "longitude": lead.longitude,
        "issue_date": lead.issue_date.isoformat(),
        "estimated_value": lead.estimated_value,
        "project_scale": lead.project_scale.value,
        "permit_number": lead.permit_number,
        "status": lead.status.value,
        "verified": lead.verified,
        "ownership_category": lead.ownership_category,
        "certification_details": lead.certification_details,
        "source_url": lead.source_url,
        "municipal_source_url": lead.municipal_source_url,
        "municipal_contact_name": lead.municipal_contact_name,
        "municipal_contact_phone": lead.municipal_contact_phone,
        "municipal_contact_email": lead.municipal_contact_email,
    }


@mcp.tool()
def find_contractors(
    trade: str,
    zip_code: str,
    radius_miles: int = 100,
    ownership_filter: str | None = None,
) -> list[dict]:
    """Find active contractors by trade, service radius, ZIP, and ownership category."""
    try:
        trade_enum = Trade(trade.lower())
        origin_lat, origin_lon = resolve_location(zip_code)
    except (ValueError, LocationNotFoundError) as exc:
        return [{"error": str(exc)}]

    matches = []
    for contractor in _db.query(Contractor).filter(Contractor.active.is_(True)).all():
        if trade_enum.value not in contractor.trades:
            continue
        if ownership_filter and contractor.ownership_category.lower() != ownership_filter.strip().lower():
            continue
        distance = haversine_miles(origin_lat, origin_lon, contractor.latitude, contractor.longitude)
        if distance <= min(radius_miles, contractor.service_radius_miles):
            matches.append({
                "id": contractor.id,
                "business_name": contractor.business_name,
                "trade": trade_enum.value,
                "distance_miles": round(distance, 2),
                "email": contractor.email,
                "phone": contractor.phone,
                "ownership_category": contractor.ownership_category,
                "certification_details": contractor.certification_details,
                "source_url": contractor.source_url,
            })
    return sorted(matches, key=lambda match: match["distance_miles"])


@mcp.tool()
def queue_outreach(
    lead_id: str,
    contractor_id: str,
    channel: str,
    message: str,
    confirmed: bool = False,
) -> dict:
    """Queue an outreach record; requires explicit confirmation and does not send externally."""
    if not confirmed:
        return {"error": "Explicit confirmation is required before outreach is queued"}
    if crud.get_lead(_db, lead_id) is None:
        return {"error": "Lead not found"}
    if _db.get(Contractor, contractor_id) is None:
        return {"error": "Contractor not found"}
    try:
        channel_enum = OutreachChannel(channel.lower())
    except ValueError:
        return {"error": "channel must be email, sms, or phone"}

    outreach = Outreach(
        id=f"OUT-{uuid4().hex[:10].upper()}",
        lead_id=lead_id,
        contractor_id=contractor_id,
        channel=channel_enum,
        status=OutreachStatus.QUEUED,
        message=message,
    )
    _db.add(outreach)
    _db.commit()
    return {"id": outreach.id, "status": outreach.status.value, "message": outreach.message}


@mcp.tool()
def search_multistate_networking_events(
    states: list[str],
    target_groups: list[str],
    event_format: str = "all",
    days_ahead: int = 60,
) -> dict:
    """Find curated networking events for Muslim entrepreneurs and WMBE/MWBE leaders.

    target_groups: WMBE, MWBE, Muslim_Business, Supplier_Diversity, Tech_Contracting.
    states: any of NY, NJ, CT, MA, PA, DE, DC. event_format: in_person, virtual, hybrid, all.
    """
    return networking.search_events(states, target_groups, event_format, days_ahead)


@mcp.tool()
def discover_networking_event_candidates(
    states: list[str],
    target_groups: list[str],
    event_format: str = "all",
    max_results: int = 10,
) -> dict:
    """Web-search for possible events. Results are UNVERIFIED and nothing is saved."""
    return event_discovery.discover_candidates(states, target_groups, event_format, max_results)


@mcp.tool()
def confirm_networking_event(
    title: str,
    event_date: str,
    state: str,
    event_format: str,
    organizer: str,
    target_groups: list[str],
    registration_url: str,
    location: str = "",
    time: str = "",
    confirmed: bool = False,
) -> dict:
    """Save an event you have verified (date YYYY-MM-DD) to the curated list; requires confirmed=True."""
    if not confirmed:
        return {"error": "Explicit confirmation is required; verify the event on the organizer's site first"}
    return event_discovery.confirm_event(
        title, event_date, state, event_format, organizer, target_groups,
        registration_url, location, time,
    )


@mcp.tool()
def match_credentials_compatibility(
    prospect_name: str,
    industry: str,
    prospect_type: str = "potential_client",
    wmbe_or_mbe_certified: bool = False,
    muslim_owned_or_affiliated: bool = False,
    perceived_tech_needs: list[str] | None = None,
) -> dict:
    """Score (0-10) how well a prospect, partner or host fits Borough Build."""
    return networking.score_compatibility(
        prospect_name, industry, prospect_type, wmbe_or_mbe_certified,
        muslim_owned_or_affiliated, perceived_tech_needs,
    )


@mcp.tool()
def process_muse_handsfree_context(
    capture_type: str,
    raw_text_or_transcript: str,
    event_context: str = "",
) -> dict:
    """Save a business card, voice note or conversation summary captured at an event."""
    return networking.save_capture(_db, capture_type, raw_text_or_transcript, event_context)


@mcp.tool()
def generate_tailored_pitch_deck_or_followup(
    lead_name: str,
    offering_focus: str,
    lead_email: str | None = None,
    compatibility_highlights: list[str] | None = None,
) -> dict:
    """Draft a follow-up email for a lead (web_design, ai_agent_integration, full_digital_agency). Never sends."""
    return networking.draft_followup(lead_name, offering_focus, lead_email, compatibility_highlights)


@mcp.tool()
def send_report_to_telegram(report: str, confirmed: bool = False) -> dict:
    """Send a Muse-generated report to the configured Telegram chat.

    Call only when the user explicitly asks to send the report. Set confirmed=True
    only after that request; sending is an external action. Long reports are split
    into multiple Telegram messages. Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.
    """
    return telegram_reports.send_report(report, confirmed)


if __name__ == "__main__":
    mcp.run(transport="stdio")
