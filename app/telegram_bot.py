"""Inbound Telegram bot: answer questions about saved events from the chat.

One-way reminders live in telegram_reports.py. This module is the other
direction: the owner texts the bot ("events", "week", "mwbe") and it replies
from the saved-events database. Telegram calls POST /telegram/webhook (see
app/routers/telegram.py).

Safety: the bot only answers the single configured TELEGRAM_CHAT_ID chat.
Updates from any other chat are ignored silently. If TELEGRAM_WEBHOOK_SECRET
is set, the webhook additionally requires Telegram's secret-token header to
match before anything is processed.
"""
import logging
from datetime import date, timedelta

import httpx
from sqlalchemy.orm import Session

from app import telegram_reports
from app.config import settings
from app.models import Event

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Networking Events Hub — ask me about your saved events:\n"
    "\n"
    "events — your next saved events\n"
    "week — events in the next 7 days\n"
    "mwbe — saved MWBE / WMBE events\n"
    "help — this list"
)

MAX_EVENTS = 10


def send_reply(chat_id: str, text: str) -> dict:
    """Send a plain-text reply to one chat, chunked like telegram_reports."""
    if not settings.telegram_bot_token:
        return {"error": "TELEGRAM_BOT_TOKEN is not configured"}
    endpoint = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    sent_ids: list[int] = []
    for chunk in telegram_reports._split_message(text):
        try:
            response = httpx.post(endpoint, json={"chat_id": chat_id, "text": chunk}, timeout=20)
            response.raise_for_status()
            result = response.json()
        except httpx.TimeoutException:
            return {"status": "failed", "error": "Telegram request timed out"}
        except httpx.HTTPStatusError as exc:
            return {"status": "failed", "error": f"Telegram returned HTTP {exc.response.status_code}"}
        except httpx.RequestError as exc:
            return {"status": "failed", "error": f"Telegram connection failed: {type(exc).__name__}"}
        if not result.get("ok"):
            return {"status": "failed", "error": result.get("description", "Telegram rejected the message")}
        sent_ids.append(result.get("result", {}).get("message_id"))
    return {"status": "sent", "message_ids": sent_ids}


def _format_events(rows: list[Event], heading: str, empty: str) -> str:
    if not rows:
        return empty
    lines = [heading]
    for event in rows:
        when = f"{event.date} {event.time}".strip()
        place = event.location or event.state
        lines.append(f"\n{when} — {event.title}\n{place}")
    return "\n".join(lines)


def _upcoming(db: Session):
    today = date.today().isoformat()
    return db.query(Event).filter(Event.date >= today).order_by(Event.date, Event.time)


def reply_for(db: Session, text: str) -> str:
    """Map one incoming message to its reply text."""
    words = (text or "").strip().lower().split()
    command = words[0].lstrip("/").split("@")[0] if words else ""

    if command == "events":
        rows = _upcoming(db).limit(MAX_EVENTS).all()
        return _format_events(rows, "Your next saved events:", "No saved events coming up.")
    if command == "week":
        last = (date.today() + timedelta(days=7)).isoformat()
        rows = _upcoming(db).filter(Event.date <= last).limit(MAX_EVENTS).all()
        return _format_events(rows, "Events in the next 7 days:", "No saved events in the next 7 days.")
    if command in ("mwbe", "wmbe"):
        rows = [
            e for e in _upcoming(db).all()
            if {"MWBE", "WMBE"} & set(e.target_groups or [])
        ][:MAX_EVENTS]
        return _format_events(rows, "Saved MWBE / WMBE events:", "No saved MWBE/WMBE events coming up.")
    return HELP_TEXT


def handle_update(db: Session, update: dict, secret_header: str | None = None) -> dict:
    """Process one Telegram webhook update. Replies only to the owner's chat."""
    if settings.telegram_webhook_secret and secret_header != settings.telegram_webhook_secret:
        return {"ok": False, "error": "bad_secret"}

    message = (update or {}).get("message") or {}
    chat_id = str((message.get("chat") or {}).get("id", ""))
    configured = (settings.telegram_chat_id or "").strip()
    if not configured or chat_id != configured:
        return {"ok": True, "ignored": "chat not authorized"}

    result = send_reply(chat_id, reply_for(db, message.get("text") or ""))
    return {"ok": True, "reply": result}


def register_webhook() -> dict:
    """Point Telegram at this service's /telegram/webhook. Never raises."""
    try:
        if not settings.telegram_bot_token:
            return {"skipped": "TELEGRAM_BOT_TOKEN is not set"}
        base = (settings.public_base_url or "").rstrip("/")
        if not base:
            return {"skipped": "no public base URL (RENDER_EXTERNAL_URL / PUBLIC_BASE_URL unset)"}
        payload: dict = {"url": f"{base}/telegram/webhook", "allowed_updates": ["message"]}
        if settings.telegram_webhook_secret:
            payload["secret_token"] = settings.telegram_webhook_secret
        endpoint = f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook"
        result = httpx.post(endpoint, json=payload, timeout=15).json()
        if result.get("ok"):
            logger.info("Telegram webhook registered: %s", payload["url"])
            return {"registered": payload["url"]}
        logger.warning("Telegram setWebhook failed: %s", result.get("description"))
        return {"error": result.get("description", "setWebhook failed")}
    except Exception as exc:  # startup must never crash on webhook setup
        logger.warning("Telegram webhook registration failed: %s", exc)
        return {"error": type(exc).__name__}
