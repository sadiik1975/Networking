# Contractor Discovery & Matching Connector

FastAPI backend that aggregates verified local project leads (municipal
permits, commercial renovations, fit-outs) and serves them via a narrow,
idempotent OpenAPI 3.1 surface for AI agent consumption (Muse-compatible).

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- Interactive docs: `http://127.0.0.1:8000/docs`
- Machine-readable schema: `http://127.0.0.1:8000/openapi.json`
- Landing page: `http://127.0.0.1:8000/`

On first startup, a SQLite database (`leads.db`) is created and seeded with
sample verified leads across several metro areas.

## Endpoints

- `GET /health` — service status and database connectivity.
- `GET /leads/search?trade=&location=&radius_miles=&min_value=` — search leads
  by trade and geographic radius around a ZIP code or "City, ST".
- `GET /leads/{lead_id}` — deep-dive lead details for dispatch.
- `POST /companies` — persist a company profile for matchmaking; `GET /companies`
  and `GET /companies/{company_id}` list and retrieve profiles. `PATCH` and
  `DELETE /companies/{company_id}` update and remove profiles.
- `POST /match?query=...` — rank saved profiles by lightweight text cosine
  similarity. Matching is lexical, not an embedding-based semantic model; scores
  are ranking signals, not calibrated probabilities. These profile and match
  routes require `X-API-Key` (`DISPATCH_API_KEY`). The default minimum score is
  `0.3`. Add `&notify=true` to explicitly send Telegram alerts for returned
  matches after setting `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

Company profiles currently share one database namespace; this implementation
does not provide tenant isolation or tenant authentication.

## HVAC business search (OpenStreetMap)

`GET /businesses/hvac/search?location=10001&radius_miles=15&limit=50` (and the
`search_hvac_businesses` MCP tool) return real HVAC businesses mapped in
OpenStreetMap via the public Overpass API. No API key is needed. Copy
`.env.example` to `.env` to override `OVERPASS_API_URL` and related settings.
Locations: built-in ZIP/city table, or any US location when `NOMINATIM_ENABLED=true`.
Results are never substituted with sample data; coverage depends on OSM, and
missing phone/website fields are `null`. Run tests with `pytest`.

## Dispatch lifecycle API

Mutating dispatch routes require `X-API-Key`. Set `DISPATCH_API_KEY` in the
environment; the local development default is `dev-dispatch-key`.

- `POST /contractors` — create a contractor profile.
- `GET/PATCH/DELETE /contractors/{contractor_id}` — manage or deactivate a profile.
- `POST /contractors/{contractor_id}/crews` — register an active crew.
- `GET /contractors/search` — match contractors by trade, ZIP radius, and ownership.
- `GET /leads/{lead_id}/matches` — match contractors to an existing lead.
- `POST /outreach/contact` — queue an auditable outreach attempt after confirmation.
- `POST /dispatch/schedule` — create a work order after dispatch and customer confirmation.
- `POST /work-orders/{work_order_id}/status` — advance status through the strict lifecycle.

Outreach is queued, not sent, until a provider integration is configured. Scheduling
checks crew conflicts. The default lifecycle is `new -> contacted -> interested ->
assigned -> scheduled -> in_progress -> completed`; cancellation is available from
each active state.

## Ask it questions conversationally (MCP)

An MCP server (`app/mcp_server.py`) exposes `search_leads`, `get_lead`,
`find_contractors`, and `queue_outreach` as
tools so any MCP-compatible agent host (Muse, Claude Desktop, VS Code, etc.)
can query leads in plain language instead of filling in the REST params by
hand. It shares the same SQLite-backed data as the REST API.

The `send_report_to_telegram` tool sends a report to the chat configured by
`TELEGRAM_CHAT_ID` using `TELEGRAM_BOT_TOKEN`. The agent must call it with
`confirmed=true` only after the user explicitly asks to send the report. It
splits long reports into multiple messages; sending is not automatic.

Run it directly to sanity-check it starts:

```bash
python -m app.mcp_server
```

To connect it from an MCP host, point the host's server config at this
command, e.g. for Claude Desktop / VS Code `mcp.json`:

```json
{
  "mcpServers": {
    "muse-contractor-leads": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/absolute/path/to/leadagent"
    }
  }
}
```

Once connected, you can ask things like "find electrical leads within 50
miles of 10001" and the host will call `search_leads` for you.

## Render Deployment

This repository includes a Render Blueprint (`render.yaml`). To deploy it:

1. Sign in to Render and connect your GitHub account.
2. In the Render dashboard, choose **New +** → **Blueprint** and select this repository.
3. Review the `been-ventures` web service and deploy it.
4. Use the `onrender.com` URL Render assigns as the public company website.

The free web service may sleep when idle, and its local SQLite data is not
persistent across redeploys. Configure `DATABASE_URL` with a persistent
database before relying on stored production data.
