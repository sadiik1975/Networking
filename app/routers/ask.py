from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import ask_agent
from app.auth import require_api_key
from app.database import get_db

protected = APIRouter(dependencies=[Depends(require_api_key)])


class AskTurn(BaseModel):
    role: str
    content: str


class AskRequest(BaseModel):
    question: str
    history: list[AskTurn] = []


@protected.post("/ask", tags=["ask"], summary="Ask the board (chat agent)")
def ask(body: AskRequest, db: Session = Depends(get_db)) -> dict:
    result = ask_agent.ask(db, body.question, [t.model_dump() for t in body.history])
    if "error" in result:
        return {"answer": result["error"], "mode": "board"}
    return result
