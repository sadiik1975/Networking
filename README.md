# Networking Events Hub — Business Networking

The Networking Events Hub helps Borough Build and Been Ventures discover and
keep track of **business networking** events — MWBE and MBE firms, supplier
diversity, chambers of commerce and procurement — across **New York, New
Jersey, Connecticut and Massachusetts**. It serves a REST API and an MCP
endpoint for AI agent hosts.

Business only: this hub tracks rooms where businesses meet businesses.
Social, party and nightlife listings are not part of this app.

## What it does

- **Use the web board** at `/`: connect with the API key (kept only in the
  browser) to see saved events, run discovery, and ask the board what's
  coming up.
- **Discover business networking events** with Tavily web search. Search
  results are unverified candidates; check the organizer's page before saving.
- **Track plans** as discovered, interested, registered, attended or skipped.
- **Get reminders** for upcoming saved events through Telegram, only when
  explicitly confirmed.
- **Keep event captures and follow-ups.** Contact capture, business matching
  and company profile endpoints from the original app remain available for
  existing integrations.

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit
uvicorn app.main:app --reload
```

Docs: `http://127.0.0.1:8000/docs`. Run the tests with `pytest tests`.

## REST API

All routes except `/health` and `/` need `X-API-Key` (`API_KEY`).

- `GET /events`, `GET /events/discover`, `POST /events`, `PATCH /events/{id}`
- `POST /reminders/telegram`
- Legacy integrations: `/contacts`, `/compatibility`, `/companies`, `/match`

By default, event discovery searches NY, NJ, CT and MA for `MWBE`,
`Supplier_Diversity` and `B2B_Networking`. The supported states also include
PA, DE and DC. Discovery categories are `B2B_Networking`, `Small_Business`,
`Startup_Tech`, `Chamber_of_Commerce`, `WMBE`, `MWBE`, `Muslim_Business`,
`Supplier_Diversity`, `Tech_Contracting` and `Procurement_Matchmaking`. Add
`TAVILY_API_KEY` to `.env` to enable web discovery.

## MCP tools

The MCP endpoint exposes the same event, reminder and legacy integration tools.
Some tool names retain "networking" for compatibility with existing clients.

Local (stdio) for VS Code or Claude Desktop:

```json
{
  "servers": {
    "networking-events-hub": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/absolute/path/to/Networking"
    }
  }
}
```

Hosted (SSE): `https://<your-host>/mcp/sse` with `Authorization: Bearer <MCP_API_KEY>`.
The endpoint returns 503 if `MCP_API_KEY` is not set.

## Deploy on Render (free)

1. **New + → Blueprint**, pick this repo. Render reads `render.yaml` and
   generates `API_KEY` and `MCP_API_KEY`.
2. Add `TAVILY_API_KEY` (and optionally the Telegram values).
3. Keep it awake with a free monitor (for example cron-job.org or UptimeRobot) on
   `https://<service>.onrender.com/health` every 5 minutes.

Render's free plan wipes the SQLite file on every redeploy. To keep events and
contacts, set `DATABASE_URL` to a free external Postgres (Neon, Supabase).

## Free always-on hosting (Oracle Cloud Always Free)

1. Create an Always Free Ubuntu VM and open TCP ports 80 and 443 in its Security List.
2. Point a free DuckDNS name at the VM's public IP.
3. On the VM:
   ```bash
   git clone https://github.com/sadiik1975/Networking.git && cd Networking
   DOMAIN=yourname.duckdns.org bash deploy/oracle/setup.sh
   ```
4. Add `TAVILY_API_KEY` to `~/Networking/.env`, then `sudo systemctl restart networking`.

The service restarts on crash or reboot, and SQLite data stays on the VM disk.
