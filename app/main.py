from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.config import settings
from app.database import Base, SessionLocal, engine, migrate_schema
from app.mcp_auth import McpAuthMiddleware
from app.mcp_server import mcp
from app.config import validate_settings
from app.routers import businesses, dispatch, health, leads, matchmaking
from app.seed import seed_dispatch_if_empty, seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    problems = validate_settings()
    if problems:
        raise RuntimeError("Invalid configuration: " + "; ".join(problems))
    Base.metadata.create_all(bind=engine)
    migrate_schema()
    db = SessionLocal()
    try:
        seed_if_empty(db)
        seed_dispatch_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Aggregates and serves verified local project leads (municipal permits, "
        "commercial renovations, fit-outs) to AI agents via a narrow, idempotent API."
    ),
    openapi_version="3.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(leads.router)
app.include_router(dispatch.router)
app.include_router(businesses.router)
app.include_router(matchmaking.router)


# SSE transport for hosted MCP clients: GET /mcp/sse, POST /mcp/messages/
app.mount("/mcp", McpAuthMiddleware(mcp.sse_app()))


@app.get("/", include_in_schema=False)
def landing_page() -> FileResponse:
    page = Path(__file__).parent / "static" / "index.html"
    return FileResponse(page, media_type="text/html")
