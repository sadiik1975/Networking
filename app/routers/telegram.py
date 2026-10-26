from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import telegram_bot
from app.database import get_db

router = APIRouter()


@router.post("/telegram/webhook", tags=["telegram"], summary="Telegram ask-bot webhook (replies about saved events)")
def telegram_webhook(request: Request, update: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    # No x-api-key here: Telegram cannot send one. Access is controlled by
    # the chat-id check (and the optional secret header) in telegram_bot.
    result = telegram_bot.handle_update(
        db, update, request.headers.get("x-telegram-bot-api-secret-token"),
    )
    if result.get("error") == "bad_secret":
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    return {"ok": True}
