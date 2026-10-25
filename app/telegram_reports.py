"""Explicitly send Muse-generated reports to the configured Telegram chat."""
import httpx

from app.config import settings

MAX_MESSAGE_UNITS = 4000
TELEGRAM_MESSAGE_LIMIT = 4096


class TelegramDeliveryError(Exception):
    pass


def _utf16_units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _split_message(text: str) -> list[str]:
    chunks: list[str] = []
    remaining = text.strip()
    while remaining:
        if _utf16_units(remaining) <= MAX_MESSAGE_UNITS:
            chunks.append(remaining)
            break

        end = min(len(remaining), MAX_MESSAGE_UNITS)
        while end > 0 and _utf16_units(remaining[:end]) > MAX_MESSAGE_UNITS:
            end -= 1
        boundary = max(remaining.rfind("\n\n", 0, end), remaining.rfind("\n", 0, end), remaining.rfind(" ", 0, end))
        if boundary > end // 2:
            end = boundary
        chunks.append(remaining[:end].rstrip())
        remaining = remaining[end:].lstrip()
    return chunks


def send_report(report: str, confirmed: bool = False) -> dict:
    if not confirmed:
        return {"error": "Explicit confirmation is required before sending a report to Telegram"}
    if not report.strip():
        return {"error": "Report must not be empty"}
    if not settings.telegram_bot_token:
        return {"error": "TELEGRAM_BOT_TOKEN is not configured"}
    if not settings.telegram_chat_id:
        return {"error": "TELEGRAM_CHAT_ID is not configured"}

    chunks = _split_message(report)
    sent_message_ids: list[int] = []
    endpoint = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

    for index, chunk in enumerate(chunks, start=1):
        if _utf16_units(chunk) > TELEGRAM_MESSAGE_LIMIT:
            return {"error": "Report chunk exceeds Telegram's message limit"}
        try:
            response = httpx.post(
                endpoint,
                json={"chat_id": settings.telegram_chat_id, "text": chunk},
                timeout=20,
            )
            response.raise_for_status()
            result = response.json()
        except httpx.TimeoutException:
            return {
                "status": "partial" if sent_message_ids else "failed",
                "sent_chunks": len(sent_message_ids),
                "total_chunks": len(chunks),
                "error": f"Telegram request timed out on chunk {index}",
            }
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            return {
                "status": "partial" if sent_message_ids else "failed",
                "sent_chunks": len(sent_message_ids),
                "total_chunks": len(chunks),
                "error": f"Telegram returned HTTP {status} on chunk {index}",
            }
        except httpx.RequestError as exc:
            return {
                "status": "partial" if sent_message_ids else "failed",
                "sent_chunks": len(sent_message_ids),
                "total_chunks": len(chunks),
                "error": f"Telegram connection failed on chunk {index}: {type(exc).__name__}",
            }

        if not result.get("ok"):
            description = result.get("description", "Telegram rejected the message")
            return {
                "status": "partial" if sent_message_ids else "failed",
                "sent_chunks": len(sent_message_ids),
                "total_chunks": len(chunks),
                "error": f"Telegram rejected chunk {index}: {description}",
            }
        sent_message_ids.append(result.get("result", {}).get("message_id"))

    return {
        "status": "sent",
        "sent_chunks": len(sent_message_ids),
        "total_chunks": len(chunks),
        "message_ids": sent_message_ids,
    }
