"""Visitor assistant endpoint — POST /agent/ask (public).

The public counterpart to the owner's key-gated POST /ask: no key is
accepted or used here, and the brain (app.visitor_agent) has no access
to the saved-events board. It answers from a fixed fact sheet and
captures join-the-list signups. Rate-limited per IP like the other
public surfaces.
"""
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import visitor_agent
from app.database import get_db

router = APIRouter(tags=["agent"])

RATE_LIMIT_PER_MINUTE = 30
_RATE_WINDOW_SECONDS = 60.0

_hits: dict[str, deque[float]] = defaultdict(deque)


def _rate_limited(ip: str) -> bool:
    now = time.monotonic()
    bucket = _hits[ip]
    while bucket and now - bucket[0] > _RATE_WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_PER_MINUTE:
        return True
    bucket.append(now)
    return False


class AgentState(BaseModel):
    step: str | None = None
    data: dict[str, str] = {}


class AgentAskRequest(BaseModel):
    message: str = ""
    state: AgentState | None = None


@router.post(
    "/agent/ask",
    summary="Visitor assistant (public; fact sheet + join-the-list capture)",
)
def agent_ask(
    payload: AgentAskRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    if _rate_limited(client_ip):
        return JSONResponse(
            status_code=429,
            content={
                "reply": "That's a lot of questions at once — give it a minute and try again.",
                "state": {"step": None, "data": {}},
            },
        )
    state = payload.state.model_dump() if payload.state else None
    return visitor_agent.ask_visitor(db, payload.message, state)
