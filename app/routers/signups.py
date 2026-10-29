"""Join-the-list signup capture — POST /signups + GET /signups.

The public half of the Hub's front door: a visitor leaves name, email,
optional company/organization, and what brings them (their business, an
organization, or curiosity) to join the list for when access opens.
There are no accounts here, no prices, no dates — just the list.

- POST /signups is public (no key): it is a form. It is validated by
  hand so every failure is a friendly JSON error, it is rate-limited
  per IP, and it deduplicates by email (case-insensitive): a repeat
  signup updates the row and returns 200, never a duplicate.
- GET /signups is owner data and sits behind the app's X-API-Key, the
  same tier as the rest of the Hub's API — no valid key, 401. Signups
  are never served by any other endpoint; the visitor agent writes
  through save_signup() but can never read the list back.
"""
import re
import time
from collections import defaultdict, deque
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.database import get_db
from app.signup_models import SIGNUP_INTERESTS, Signup

router = APIRouter(tags=["signups"])

RATE_LIMIT_PER_MINUTE = 10
_RATE_WINDOW_SECONDS = 60.0

# ip -> deque of request timestamps (seconds). Same in-memory pattern as
# the other public limiters: a restart resetting the buckets is harmless.
_hits: dict[str, deque[float]] = defaultdict(deque)

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _rate_limited(ip: str) -> bool:
    now = time.monotonic()
    bucket = _hits[ip]
    while bucket and now - bucket[0] > _RATE_WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_PER_MINUTE:
        return True
    bucket.append(now)
    return False


def _error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"ok": False, "error": message})


def normalize_interest(text: str | None) -> str | None:
    """Map a canonical value or a plain-words label to an interest value.

    Accepts the stored values ("business", "organization", "curious")
    and the labels a visitor would actually say ("my business",
    "an organization", "just curious"). Returns None when nothing fits.
    """
    t = (text or "").strip().lower()
    if t in SIGNUP_INTERESTS:
        return t
    if any(w in t for w in ("organization", "organisation", "chamber", "association", "agency", "nonprofit", "non-profit")):
        return "organization"
    if any(w in t for w in ("curious", "curiosity", "looking", "browsing", "exploring")):
        return "curious"
    if any(w in t for w in ("business", "company", "my own", "owner", "firm")):
        return "business"
    return None


def save_signup(
    db: Session, *, name: str, email: str, company: str, interest: str
) -> bool:
    """Insert or update a list signup, deduplicated by email.

    The one storage path for signups: POST /signups and the visitor
    agent's in-chat capture both land here. Inputs are expected
    pre-validated and normalized (email lowercased). Returns True when
    a new row was created, False when an existing row was updated.
    """
    existing = db.query(Signup).filter(Signup.email == email).first()
    if existing is not None:
        existing.name = name
        existing.company = company
        existing.interest = interest
        existing.updated_at = datetime.utcnow()
        db.commit()
        return False
    db.add(Signup(name=name, email=email, company=company, interest=interest))
    db.commit()
    return True


class SignupRequest(BaseModel):
    name: str = ""
    email: str = ""
    company: str = ""
    interest: str = ""


class SignupOut(BaseModel):
    id: int
    name: str
    email: str
    company: str
    interest: str
    created_at: datetime
    updated_at: datetime


@router.post(
    "/signups",
    summary="Join the list from the public page (public, deduplicated by email)",
)
def create_signup(
    payload: SignupRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    if _rate_limited(client_ip):
        return _error(
            429,
            "Too many signups from this connection — give it a minute and try again.",
        )

    name = (payload.name or "").strip()
    email = (payload.email or "").strip().lower()
    company = (payload.company or "").strip()
    interest = normalize_interest(payload.interest)

    if not name:
        return _error(422, "Please enter your full name.")
    if not _EMAIL_PATTERN.match(email):
        return _error(422, "That email doesn't look right — check it and try again.")
    if interest is None:
        return _error(422, "Please choose what fits you best — your business, an organization, or just curious.")

    created = save_signup(db, name=name, email=email, company=company, interest=interest)
    return JSONResponse(status_code=201 if created else 200, content={"ok": True})


@router.get(
    "/signups",
    response_model=list[SignupOut],
    summary="List join-the-list signups, newest first (API key required)",
    dependencies=[Depends(require_api_key)],
)
def list_signups(db: Session = Depends(get_db)):
    return (
        db.query(Signup)
        .order_by(Signup.created_at.desc(), Signup.id.desc())
        .all()
    )
