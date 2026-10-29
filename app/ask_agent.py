"""Ask-the-board chat agent for the Networking Events Hub.

POST /ask answers questions about the owner's business networking board.
Two modes:

- AI mode (AI_API_KEY set): an OpenAI-compatible chat model (default xAI
  Grok) with three tools — search the saved board, discover new events on
  the web, and save an event. Saving is guarded: the save tool refuses
  unless the model passes confirmed=true, which the system prompt allows
  only after the user explicitly agreed to that exact event.
- Board mode (no key, or the AI call fails): deterministic answers from
  the saved events, the same intents the Telegram ask-bot understands.
"""

import json

import httpx
from sqlalchemy.orm import Session

from app import event_discovery, events
from app.config import settings

SYSTEM_PROMPT = """You are the assistant inside the Networking Events Hub, a business \
networking board for Borough Build and Been Ventures Inc (owner: Sadeek Been).

Your job: help Sadeek find, track and choose BUSINESS networking events — \
MWBE/MBE firms, supplier diversity, chambers of commerce, procurement and \
matchmaking. Business only: never suggest social, party or nightlife events.

His schedule: he works night shifts (7 PM-7 AM) every Wednesday, Thursday and \
Friday night, plus every other Saturday night. He is always off Sunday, Monday \
and Tuesday. When you mention an event, flag it if it collides with a work night.

Rules:
- Never invent events, dates, times, places or prices. Only use tool results.
- Discovery results are UNVERIFIED web hits. Say so, and tell him to open the \
organizer's page to check before anything is saved.
- Never save an event unless Sadeek has explicitly said yes to that exact \
event in this conversation. To save, call save_event with confirmed=true. \
Without his yes, present the event and ask first.
- Keep answers short and plain, with one clear next step. List events as: \
date — title (place).
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_saved_events",
            "description": "Search the owner's saved board of business networking events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {"type": "integer", "description": "Look ahead window in days (default 60)."},
                    "target_groups": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional subset of: MWBE, WMBE, Supplier_Diversity, Procurement_Matchmaking, B2B_Networking, Chamber_of_Commerce, Small_Business, Startup_Tech, Tech_Contracting, Muslim_Business.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "discover_events",
            "description": "Web-search for NEW business networking event candidates (unverified). Use when the user asks to find events that are not on the board yet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_groups": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Business categories to search (same list as search_saved_events).",
                    },
                    "states": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional state codes, e.g. [\"NY\"].",
                    },
                    "max_results": {"type": "integer", "description": "Per category (default 5, max 20)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_event",
            "description": "Save a verified event to the board. ONLY call with confirmed=true after the user explicitly agreed to save this exact event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "event_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "state": {"type": "string", "description": "Two-letter state code."},
                    "event_format": {"type": "string", "enum": ["in_person", "virtual", "hybrid"]},
                    "organizer": {"type": "string"},
                    "registration_url": {"type": "string"},
                    "location": {"type": "string"},
                    "time": {"type": "string"},
                    "target_groups": {"type": "array", "items": {"type": "string"}},
                    "confirmed": {"type": "boolean", "description": "Must be true, and only after the user's explicit yes."},
                },
                "required": ["title", "event_date", "state", "event_format", "organizer", "registration_url", "confirmed"],
            },
        },
    },
]


def _exec_tool(db: Session, name: str, args: dict) -> tuple[dict, dict]:
    """Run one tool call. Returns (result_for_model, ui_extras)."""
    if name == "search_saved_events":
        result = events.search_events(
            db,
            target_groups=args.get("target_groups") or None,
            days_ahead=int(args.get("days_ahead") or 60),
        )
        return result, {"events": result.get("events", [])}
    if name == "discover_events":
        result = event_discovery.discover_candidates(
            states=args.get("states") or None,
            target_groups=args.get("target_groups") or None,
            max_results=int(args.get("max_results") or 5),
        )
        return result, {"candidates": result.get("candidates", [])}
    if name == "save_event":
        if not args.get("confirmed"):
            return {
                "error": "Not saved. Saving needs the user's explicit yes to this exact event first. Present the event and ask."
            }, {}
        result = events.add_event(
            db,
            args.get("title", ""),
            args.get("event_date", ""),
            args.get("state", ""),
            args.get("event_format", ""),
            args.get("organizer", ""),
            args.get("registration_url", ""),
            args.get("target_groups"),
            args.get("location", ""),
            args.get("time", ""),
        )
        return result, {}
    return {"error": f"unknown tool {name}"}, {}


def _format_rows(rows: list[dict], heading: str, empty: str) -> str:
    if not rows:
        return empty
    lines = [heading]
    for e in rows:
        when = f"{e['date']} {e['time']}".strip()
        place = e["location"] or e["format"].replace("_", " ")
        lines.append(f"\n{when} — {e['title']}\n{place} ({e['state']})\n{e['registration_url']}")
    return "\n".join(lines)


def board_answer(db: Session, question: str) -> dict:
    """Deterministic fallback: answer from the saved board, no AI."""
    q = question.lower()
    if "week" in q:
        result = events.search_events(db, days_ahead=7)
        text = _format_rows(result.get("events", []), "On your board in the next 7 days:",
                            "Nothing on your board in the next 7 days.")
        return {"answer": text, "mode": "board", "events": result.get("events", [])}
    if any(w in q for w in ("mwbe", "wmbe", "mbe", "supplier", "diversity", "procurement", "matchmaking", "chamber")):
        result = events.search_events(
            db, target_groups=["MWBE", "WMBE", "Supplier_Diversity", "Procurement_Matchmaking", "Chamber_of_Commerce"],
            days_ahead=90,
        )
        text = _format_rows(result.get("events", []), "MWBE / supplier-diversity / procurement events on your board:",
                            "No MWBE-type events on your board right now. Try Find new rooms to discover some.")
        return {"answer": text, "mode": "board", "events": result.get("events", [])}
    result = events.search_events(db, days_ahead=60)
    text = _format_rows(result.get("events", []), "Coming up on your board:",
                        "Your board is empty for the next 60 days. Use Find new rooms to discover candidates.")
    if any(w in q for w in ("should", "recommend", "best", "advice", "what do i do", "what to do")):
        text = ("The AI side of Ask isn't switched on yet (no AI key on the server), "
                "so here's your board — you pick:\n\n" + text)
    return {"answer": text, "mode": "board", "events": result.get("events", [])}


def _ai_answer(db: Session, question: str, history: list[dict]) -> dict:
    api_key = (settings.ai_api_key or "").strip()
    base = (settings.ai_base_url or "https://api.x.ai/v1").rstrip("/")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history[-6:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": str(turn["content"])[:2000]})
    messages.append({"role": "user", "content": question})

    ui: dict = {}
    with httpx.Client(trust_env=False, timeout=60) as client:
        for _ in range(4):
            response = client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": settings.ai_model, "messages": messages, "tools": TOOLS, "tool_choice": "auto"},
            )
            if response.status_code >= 400:
                raise RuntimeError(f"AI returned HTTP {response.status_code}")
            message = response.json()["choices"][0]["message"]
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                return {"answer": (message.get("content") or "").strip() or "I didn't get an answer back — try again.", "mode": "ai", **ui}
            messages.append(message)
            for call in tool_calls:
                fn = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                result, extras = _exec_tool(db, fn, args)
                ui.update({k: v for k, v in extras.items() if v})
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result)[:6000],
                })
    return {"answer": "That took too many steps — try asking it a simpler way.", "mode": "ai", **ui}


def ask(db: Session, question: str, history: list[dict] | None = None) -> dict:
    question = (question or "").strip()
    if not question:
        return {"error": "Ask a question first."}
    if (settings.ai_api_key or "").strip():
        try:
            return _ai_answer(db, question, history or [])
        except Exception:
            fallback = board_answer(db, question)
            fallback["answer"] = "(The AI was unreachable, so I answered from your board.)\n\n" + fallback["answer"]
            return fallback
    return board_answer(db, question)
