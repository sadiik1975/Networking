from contextlib import asynccontextmanager
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
        "Find, track and follow up on B2B networking events for Borough Build and "
        "Been Ventures. Also available to AI agents over MCP at /mcp/sse."
    ),
    openapi_version="3.1.0",
    lifespan=lifespan,
)

app.include_router(events.router)
app.include_router(matchmaking.router)

# SSE transport for hosted MCP clients: GET /mcp/sse, POST /mcp/messages/
app.mount("/mcp", McpAuthMiddleware(mcp.sse_app()))


@app.get("/", include_in_schema=False)
def landing_page() -> FileResponse:
    page = Path(__file__).parent / "static" / "index.html"
    return FileResponse(page, media_type="text/html")
