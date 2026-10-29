"""Visitor assistant for the Networking Events Hub — POST /agent/ask.

The PUBLIC chat on the Hub's page, for people who arrive with no API
key. It is a separate, deliberately smaller brain than the owner's
Ask agent (POST /ask):

- It answers from the fixed fact sheet below — the ONLY facts about
  the Hub it may state. No invented events, dates, prices or features.
- It has NO access to the owner's saved-events board or any owner
  data: nothing in this module reads the events tables, and asks about
  saved events get a privacy deflection, never data.
- It captures join-the-list signups in-chat, through the same storage
  function as POST /signups (app.routers.signups.save_signup).

The brain is deterministic: scripted flow + intent matching. If
AI_API_KEY is configured (the same OpenAI-compatible settings /ask
uses), the model may answer free-form questions the script doesn't
match, inside the same fact sheet — no tools, no board access — and
any AI failure falls back to the scripted deflection. Every structured
path (facts, pricing, privacy, capture) stays scripted either way.
"""

import re

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.routers.signups import _EMAIL_PATTERN, normalize_interest, save_signup

# --- The fact sheet: the only facts this agent may state. -------------

CATEGORIES_LINE = (
    "MWBE and MBE business networking, supplier-diversity rooms, "
    "chambers of commerce, and procurement matchmaking"
)

GREETING_REPLY = (
    "Hi — I'm the visitor assistant for the Networking Events Hub. "
    "I can explain what this hub is, what kinds of business rooms it "
    "tracks, or add you to the list for when access opens. What would "
    "you like to know?"
)

WHAT_REPLY = (
    "The Networking Events Hub — from Borough Build / Been Ventures "
    "Inc — finds business networking rooms: " + CATEGORIES_LINE + ". "
    "Business only: it never lists parties or social mixers. The hub "
    "keeps a saved board of events, discovers new rooms, and answers "
    "questions about the board. Right now it's the owner's working "
    "tool — access for other businesses is in the works, and the way "
    "in is the list. Say \u201cjoin\u201d and I'll add you."
)

HOW_REPLY = (
    "Here's how it works: the hub tracks business networking events "
    "across categories like " + CATEGORIES_LINE + ". Events it finds "
    "go on a saved board, new rooms can be discovered by category, "
    "and the owner asks the board questions in plain words — what's "
    "this week, which rooms are MWBE, what to do next. Access for "
    "other businesses, and boards of their own for organizations, "
    "are in the works — join the list and you'll hear when it opens."
)

WHO_REPLY = (
    "Two kinds of people, mainly. Business owners who network for "
    "contracts — MWBE and MBE firms, contractors, and suppliers who "
    "need to be in supplier-diversity and procurement rooms. And "
    "organizations that run business communities — chambers of "
    "commerce, associations, and agencies — who could run a board "
    "like this for their own members. If either sounds like you, "
    "say \u201cjoin\u201d and I'll put you on the list."
)

KINDS_REPLY = (
    "The hub tracks business rooms in these categories: "
    + CATEGORIES_LINE + " — plus general B2B and small-business "
    "networking. Business only: parties, social mixers, and "
    "nightlife never make the board."
)

ACCESS_REPLY = (
    "Right now the Hub is the owner's working tool, so there aren't "
    "public accounts yet. Access for other businesses — and boards "
    "for organizations like chambers, associations, and agencies — "
    "is in the works. The way in is the list: say \u201cjoin\u201d "
    "and I'll add you, and you'll hear first when access opens."
)

PRICING_REPLY = (
    "Pricing hasn't been announced — join the list and you'll hear "
    "first. Say \u201cjoin\u201d and I'll add you — it takes about "
    "thirty seconds."
)

PRIVACY_REPLY = (
    "The saved board is the owner's private workspace — I can't show "
    "what's on it, and I don't have access to it from here. What I "
    "can do is explain the kinds of rooms the hub tracks, or add you "
    "to the list so you can have a board of your own when access "
    "opens. Say \u201cjoin\u201d if you'd like that."
)

DEFLECTION_REPLY = (
    "I can help with the Networking Events Hub — what it is, how it "
    "works, who it's for, the kinds of business rooms it tracks, or "
    "joining the list for when access opens. What would you like?"
)

SIGNUP_START_REPLY = (
    "Great — let's get you on the list. What's your full name?"
)

AI_SYSTEM_PROMPT = (
    "You are the visitor assistant on the public page of the "
    "Networking Events Hub, a tool from Borough Build / Been "
    "Ventures Inc. Answer ONLY from these facts: the Hub finds "
    "business networking rooms — MWBE and MBE business networking, "
    "supplier-diversity rooms, chambers of commerce, and procurement "
    "matchmaking. Business only; it never lists parties or social "
    "mixers. It keeps a saved board of events, discovers new rooms, "
    "and answers questions about the board. It is currently the "
    "owner's working tool; access for other businesses and boards "
    "for organizations (chambers, associations, agencies) are in the "
    "works, and the way in is the list. Pricing has not been "
    "announced. Never invent events, dates, prices, or features. "
    "You have NO access to the saved board: never claim to know what "
    "is on it, and never share anything about the owner's schedule "
    "or personal details. Keep answers short and plain, and when it "
    "fits, suggest joining the list (the visitor can say \u201cjoin\u201d)."
)

# --- Intent patterns ----------------------------------------------------

_PRICING = re.compile(
    r"\bpric\w*\b|\bcost\w*\b|how much|\bfee\b|\bfees\b|subscription|"
    r"\bpay\b|\bpaid\b|\bcharge\w*\b|free\b"
)
_PRIVACY = re.compile(
    r"saved|on (your|the|his|her) board|your board|your events|"
    r"what'?s on|what is on|show me (the|your)|owner'?s|his schedule|"
    r"her schedule|your schedule|personal"
)
_JOIN = re.compile(
    r"sign me up|sign ?up|join|get started|i want in|notify me|"
    r"wait ?list|add me|put me on|count me in"
)
_ACCESS = re.compile(
    r"can i use|how (do|can) i (use|get|access)|get access|access\b|"
    r"open an account|create an account|register|log ?in"
)
_WHAT = re.compile(
    r"what is (this|it)|what'?s this|what do you do|tell me about|"
    r"about (this|the hub)|explain"
)
_HOW = re.compile(r"how does (it|this|the hub) work|how it works|how do i use")
_WHO = re.compile(
    r"who is (it|this) for|who can|who uses|is (it|this) for me|"
    r"for (businesses|organizations|organisations|chambers)"
)
_KINDS = re.compile(
    r"(kind|type|categor)\w* of|what (events|rooms)|which (events|rooms)|"
    r"kinds|types|categories"
)
_GREETING = re.compile(
    r"^\s*(hi|hiya|hello|hey|yo|good (morning|afternoon|evening))\b"
)
_CANCEL = re.compile(r"^\s*(cancel|stop|never ?mind|quit|exit|forget it)\b")
_SKIP = re.compile(r"^\s*(skip|none|no|n/a|rather not|pass)\s*\.?$")

_CAPTURE_STEPS = {"name", "email", "company", "interest"}
_DATA_KEYS = ("name", "email", "company")


def clean_state(raw: object) -> dict:
    """Trust nothing about the echoed state: known steps and keys only."""
    if not isinstance(raw, dict):
        return {"step": None, "data": {}}
    step = raw.get("step")
    if step not in _CAPTURE_STEPS:
        return {"step": None, "data": {}}
    data_in = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    data = {
        key: str(data_in[key])[:200]
        for key in _DATA_KEYS
        if data_in.get(key)
    }
    return {"step": step, "data": data}


def _reply(text: str, state: dict | None = None) -> dict:
    return {"reply": text, "state": state or {"step": None, "data": {}}}


# --- Signup capture flow ---------------------------------------------------


def _capture_reply(db: Session, message: str, state: dict) -> dict:
    text = (message or "").strip()
    step = state["step"]
    data = dict(state["data"])

    if _CANCEL.search(text.lower()):
        return _reply(
            "No problem — I've stopped there. Ask me anything about "
            "the Hub, or say \u201cjoin\u201d whenever you're ready."
        )

    if step == "name":
        if len(text) < 2:
            return _reply("I didn't catch that — what's your full name?", state)
        data["name"] = text
        first = text.split()[0]
        return _reply(
            f"Thanks, {first}. What's your email address?",
            {"step": "email", "data": data},
        )

    if step == "email":
        email = text.lower()
        if not _EMAIL_PATTERN.match(email):
            return _reply(
                "That email doesn't look right — check it and send it again?",
                state,
            )
        data["email"] = email
        return _reply(
            "Got it. What's your company or organization? "
            "(Say \u201cskip\u201d if you'd rather not say.)",
            {"step": "company", "data": data},
        )

    if step == "company":
        data["company"] = "" if _SKIP.search(text.lower()) else text[:200]
        return _reply(
            "Last one — which fits you best: are you here for "
            "\u201cmy business\u201d, for \u201can organization\u201d "
            "(a chamber, association, or agency), or \u201cjust "
            "curious\u201d?",
            {"step": "interest", "data": data},
        )

    if step == "interest":
        interest = normalize_interest(text)
        if interest is None:
            return _reply(
                "I didn't quite get that — which fits best: "
                "\u201cmy business\u201d, \u201can organization\u201d, "
                "or \u201cjust curious\u201d?",
                state,
            )
        save_signup(
            db,
            name=data.get("name", ""),
            email=data.get("email", ""),
            company=data.get("company", ""),
            interest=interest,
        )
        first = (data.get("name") or "there").split()[0]
        return _reply(
            f"You're on the list, {first}. When access opens — for "
            "businesses, and boards for organizations — you'll hear "
            "first. Anything else you'd like to know about the Hub?"
        )

    return _reply(DEFLECTION_REPLY)


# --- Scripted intents --------------------------------------------------------


def _scripted_reply(db: Session, message: str, state: dict) -> dict | None:
    """Return a reply for a matched intent, or None to fall through
    to the (optional) AI answer / deflection."""
    q = (message or "").strip().lower()
    if not q:
        return _reply(GREETING_REPLY)

    if _PRICING.search(q):
        return _reply(PRICING_REPLY)
    if _PRIVACY.search(q):
        return _reply(PRIVACY_REPLY)
    if _JOIN.search(q):
        return _reply(SIGNUP_START_REPLY, {"step": "name", "data": {}})
    if _ACCESS.search(q):
        return _reply(ACCESS_REPLY)
    if _WHAT.search(q):
        return _reply(WHAT_REPLY)
    if _HOW.search(q):
        return _reply(HOW_REPLY)
    if _WHO.search(q):
        return _reply(WHO_REPLY)
    if _KINDS.search(q):
        return _reply(KINDS_REPLY)
    if _GREETING.search(q):
        return _reply(GREETING_REPLY)
    return None


def _ai_reply(message: str) -> str | None:
    """Optional fact-sheet-only AI answer for unmatched questions.

    No tools, no board access — the model only ever sees the fact
    sheet system prompt and the visitor's message. Returns None on
    any failure so the caller falls back to the scripted deflection.
    """
    api_key = (settings.ai_api_key or "").strip()
    if not api_key:
        return None
    base = (settings.ai_base_url or "https://api.x.ai/v1").rstrip("/")
    try:
        with httpx.Client(trust_env=False, timeout=30) as client:
            response = client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": settings.ai_model,
                    "messages": [
                        {"role": "system", "content": AI_SYSTEM_PROMPT},
                        {"role": "user", "content": message[:2000]},
                    ],
                },
            )
        if response.status_code >= 400:
            return None
        content = (response.json()["choices"][0]["message"].get("content") or "").strip()
        return content or None
    except Exception:
        return None


def ask_visitor(db: Session, message: str, state: dict | None) -> dict:
    """One turn of the visitor assistant. Never touches the events
    tables — db is used only for saving a completed signup."""
    clean = clean_state(state)
    if clean["step"] is not None:
        return _capture_reply(db, message, clean)
    scripted = _scripted_reply(db, message, clean)
    if scripted is not None:
        return scripted
    ai_text = _ai_reply((message or "").strip())
    if ai_text:
        return _reply(ai_text)
    return _reply(DEFLECTION_REPLY)
