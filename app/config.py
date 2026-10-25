import os
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Runtime configuration, overridable via environment variables."""

    app_name: str = "Muse Contractor Lead & Dispatch Connector"
    app_version: str = "1.0.0"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./leads.db")
    max_search_results: int = int(os.getenv("MAX_SEARCH_RESULTS", "50"))
    dispatch_api_key: str = os.getenv("DISPATCH_API_KEY", "dev-dispatch-key")

    # Shared secret required to call the hosted MCP endpoint (/mcp).
    mcp_api_key: str | None = os.getenv("MCP_API_KEY") or None

    # Public Overpass endpoints need no API key; this is an endpoint, not a secret.
    overpass_api_url: str = os.getenv("OVERPASS_API_URL", "https://overpass-api.de/api/interpreter")
    overpass_timeout_seconds: float = float(os.getenv("OVERPASS_TIMEOUT_SECONDS", "60"))
    overpass_max_retries: int = int(os.getenv("OVERPASS_MAX_RETRIES", "2"))
    overpass_cache_ttl_seconds: int = int(os.getenv("OVERPASS_CACHE_TTL_SECONDS", "900"))
    # Identifies this app to public OSM services, as their usage policies require.
    osm_user_agent: str = os.getenv("OSM_USER_AGENT", "muse-contractor-leads/1.0 (https://been-ventures.onrender.com)")

    # Optional free geocoder for locations outside the built-in ZIP table.
    nominatim_enabled: bool = os.getenv("NOMINATIM_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
    nominatim_api_url: str = os.getenv("NOMINATIM_API_URL", "https://nominatim.openstreetmap.org/search")

    # Only used by networking event discovery (Tavily web search).
    tavily_api_key: str | None = os.getenv("TAVILY_API_KEY") or None
    tavily_api_url: str = os.getenv("TAVILY_API_URL", "https://api.tavily.com/search")

    # Optional integration; business search never reads it.
    telegram_bot_token: str | None = os.getenv("TELEGRAM_BOT_TOKEN") or None
    telegram_chat_id: str | None = os.getenv("TELEGRAM_CHAT_ID") or None


settings = Settings()


def validate_settings(current: Settings = settings) -> list[str]:
    """Return names of invalid variables (never their values)."""
    problems: list[str] = []
    for name, value in (
        ("OVERPASS_API_URL", current.overpass_api_url),
        ("NOMINATIM_API_URL", current.nominatim_api_url),
    ):
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            problems.append(f"{name} must be an http(s) URL")
    if current.overpass_timeout_seconds <= 0:
        problems.append("OVERPASS_TIMEOUT_SECONDS must be positive")
    if current.overpass_max_retries < 0:
        problems.append("OVERPASS_MAX_RETRIES must be zero or greater")
    return problems
