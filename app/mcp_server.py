"""MCP server exposing After Hours event tools to an agent host (Muse, Claude Desktop, VS Code).

Run locally with `python -m app.mcp_server` (stdio). When hosted, the same tools
are served over SSE at /mcp/sse by app.main.
"""
from contextlib import contextmanager

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from app import event_discovery, events, networking, telegram_reports
from app.database import SessionLocal, init_db

# Allow public hostnames when hosted; the default only accepts localhost Host headers.
mcp = FastMCP(
    "after-hours-nightlife",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

init_db()


@contextmanager
def _session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@mcp.tool()
def search_networking_events(
    states: list[str] | None = None,
    target_groups: list[str] | None = None,
    event_format: str = "all",
    days_ahead: int = 60,
    statuses: list[str] | None = None,
) -> dict:
    """List saved upcoming nightlife and music events.

    states: any of NY, NJ, CT, MA, PA, DE, DC (default NY, NJ, CT and MA).
    target_groups: Nightlife, Hip_Hop, R_and_B, Latin, Afrobeats, Live_Music, Lounges,
        Concerts, Parties, or legacy business categories (default Nightlife).
    event_format: in_person, virtual, hybrid, all.
    statuses: discovered, interested, registered, attended, skipped (default any).
    """
    with _session() as db:
        return events.search_events(db, states, target_groups, event_format, days_ahead, statuses)


@mcp.tool()
def discover_networking_event_candidates(
    states: list[str] | None = None,
    target_groups: list[str] | None = None,
    event_format: str = "all",
    max_results: int = 10,
) -> dict:
    """Web-search for nightlife and music event candidates. Results are unverified and not saved."""
    return event_discovery.discover_candidates(states, target_groups, event_format, max_results)


@mcp.tool()
def confirm_networking_event(
    title: str,
    event_date: str,
    state: str,
    event_format: str,
    organizer: str,
    registration_url: str,
    target_groups: list[str] | None = None,
    location: str = "",
    time: str = "",
    brand: str | None = None,
    status: str = "interested",
    confirmed: bool = False,
) -> dict:
    """Save an event you have verified (date YYYY-MM-DD); requires confirmed=True.

    brand: borough_build or been_ventures (which company will attend).
    status: discovered, interested, registered, attended, skipped.
    """
    if not confirmed:
        return {"error": "Explicit confirmation is required; verify the event on the organizer's site first"}
    with _session() as db:
        return events.add_event(
            db, title, event_date, state, event_format, organizer, registration_url,
            target_groups, location, time, status, brand,
        )


@mcp.tool()
def update_networking_event(event_id: str, status: str | None = None, brand: str | None = None, notes: str | None = None) -> dict:
    """Mark an event interested, registered, attended or skipped; assign a brand; add notes."""
    with _session() as db:
        return events.update_event(db, event_id, status, notes, brand)


@mcp.tool()
def process_muse_handsfree_context(
    capture_type: str,
    raw_text_or_transcript: str,
    event_context: str = "",
    event_id: str | None = None,
    name: str | None = None,
    company: str | None = None,
    brand: str | None = None,
) -> dict:
    """Save a business card, voice note or conversation summary captured at an event.

    capture_type: business_card_image, audio_voice_note, live_convo_summary, manual.
    """
    with _session() as db:
        return events.save_contact(
            db, capture_type, raw_text_or_transcript, event_context, event_id,
            name=name, company=company, brand=brand,
        )


@mcp.tool()
def list_networking_contacts(followup_status: str | None = None, event_id: str | None = None, limit: int = 50) -> dict:
    """List saved contacts. followup_status: new, drafted, sent, replied, closed."""
    with _session() as db:
        return events.list_contacts(db, followup_status, event_id, limit)


@mcp.tool()
def update_networking_contact(
    contact_id: str,
    followup_status: str | None = None,
    name: str | None = None,
    company: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    notes: str | None = None,
    brand: str | None = None,
) -> dict:
    """Correct contact details or move a contact through followup_status."""
    with _session() as db:
        return events.update_contact(
            db, contact_id, followup_status=followup_status, name=name, company=company,
            email=email, phone=phone, notes=notes, brand=brand,
        )


@mcp.tool()
def match_credentials_compatibility(
    brand: str,
    prospect_name: str,
    industry: str = "",
    prospect_type: str = "potential_client",
    certified_wmbe_or_mbe: bool = False,
    community_affiliated: bool = False,
    perceived_needs: list[str] | None = None,
) -> dict:
    """Score (0-10) how well a prospect fits a brand (borough_build or been_ventures).

    prospect_type: potential_client, partner, investor, prime_contractor, networking_host.
    """
    return networking.score_compatibility(
        brand, prospect_name, industry, prospect_type, certified_wmbe_or_mbe,
        community_affiliated, perceived_needs,
    )


@mcp.tool()
def generate_tailored_pitch_deck_or_followup(
    brand: str,
    contact_name: str,
    offering_focus: str,
    contact_email: str | None = None,
    highlights: list[str] | None = None,
    event_context: str = "",
    contact_id: str | None = None,
) -> dict:
    """Draft a follow-up email for borough_build or been_ventures. Never sends.

    borough_build offering_focus: web_design, ai_agent_integration, full_digital_agency.
    been_ventures offering_focus: ai_tools, partnership, platform_integration.
    Pass contact_id to use the saved contact's details and mark it drafted.
    """
    if contact_id:
        with _session() as db:
            return events.followup_for_contact(db, contact_id, brand, offering_focus, highlights)
    return networking.draft_followup(brand, contact_name, offering_focus, contact_email, highlights, event_context)


@mcp.tool()
def send_event_reminders_to_telegram(days_ahead: int = 7, confirmed: bool = False) -> dict:
    """Send upcoming interested/registered events to Telegram. Requires confirmed=True."""
    with _session() as db:
        digest = events.reminder_digest(db, days_ahead)
    if digest.get("error") or digest["count"] == 0:
        return digest
    return telegram_reports.send_report(digest["text"], confirmed) | {"events": digest["count"]}


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
