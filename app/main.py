from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db
from app.mcp_auth import McpAuthMiddleware
from app.mcp_server import mcp
from app.routers import events, matchmaking


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Discover and track hip-hop, R&B, Latin, lounge, concert and nightlife events "
        "across NY, NJ, CT and MA. Also available to AI agents over MCP at /mcp/sse."
    ),
    openapi_version="3.1.0",
    lifespan=lifespan,
)

app.include_router(events.router)
app.include_router(matchmaking.router)

# SSE transport for hosted MCP clients: GET /mcp/sse, POST /mcp/messages/
app.mount("/mcp/key/{key}", McpAuthMiddleware(mcp.sse_app()))
app.mount("/mcp", McpAuthMiddleware(mcp.sse_app()))


@app.get("/api/cron-ping", include_in_schema=False)
@app.get("/healthz", include_in_schema=False)
def cron_ping() -> dict:
    """Tiny, DB-free response for cron-job.org / uptime monitors."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds")}


@app.get("/", include_in_schema=False)
def landing_page() -> FileResponse:
    page = Path(__file__).parent / "static" / "index.html"
    return FileResponse(page, media_type="text/html")
