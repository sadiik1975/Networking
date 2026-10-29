import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Runtime configuration, overridable via environment variables."""

    app_name: str = "Networking Events Hub"
    app_version: str = "2.0.0"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./networking.db")

    # Key for the REST API. DISPATCH_API_KEY is accepted for older deployments.
    api_key: str = os.getenv("API_KEY") or os.getenv("DISPATCH_API_KEY") or "dev-api-key"
    # Key for the hosted MCP endpoint (/mcp). If unset, /mcp is closed.
    mcp_api_key: str | None = os.getenv("MCP_API_KEY") or None

    # Event discovery (Tavily web search).
    tavily_api_key: str | None = os.getenv("TAVILY_API_KEY") or None
    tavily_api_url: str = os.getenv("TAVILY_API_URL", "https://api.tavily.com/search")

    # Optional Telegram reminders and reports.
    telegram_bot_token: str | None = os.getenv("TELEGRAM_BOT_TOKEN") or None
    telegram_chat_id: str | None = os.getenv("TELEGRAM_CHAT_ID") or None
    # Optional secret Telegram echoes on every ask-bot webhook call (header
    # X-Telegram-Bot-Api-Secret-Token). If unset, only the chat-id check applies.
    telegram_webhook_secret: str | None = os.getenv("TELEGRAM_WEBHOOK_SECRET") or None
    # Public base URL of this service, used to self-register the Telegram
    # webhook on startup. Render sets RENDER_EXTERNAL_URL automatically;
    # PUBLIC_BASE_URL covers other hosts.
    public_base_url: str | None = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("PUBLIC_BASE_URL") or None

    # Public websites used in follow-up drafts.
    borough_build_url: str = os.getenv("BOROUGH_BUILD_URL", "https://boroughbuild.netlify.app/")
    been_ventures_url: str = os.getenv("BEEN_VENTURES_URL", "https://been-ventures.onrender.com/")


settings = Settings()
