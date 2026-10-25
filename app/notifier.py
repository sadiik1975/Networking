import httpx

from app.config import settings


class NotificationNotConfigured(Exception):
    pass


class NotificationError(Exception):
    pass


def send_b2b_lead_alert(company_name: str, tags: list[str], match_score: float) -> None:
    bot_token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not bot_token or not chat_id:
        raise NotificationNotConfigured("Telegram alerts require TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")

    message = (
        "New B2B match identified!\n\n"
        f"Company: {company_name}\n"
        f"Certifications and tags: {', '.join(tags)}\n"
        f"Confidence score: {match_score * 100:.1f}%"
    )
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        response = httpx.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise NotificationError("Telegram rejected the alert")
    except (httpx.HTTPError, ValueError) as exc:
        raise NotificationError("Unable to send Telegram alert") from exc
