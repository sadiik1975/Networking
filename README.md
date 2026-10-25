# Networking Events Hub

A connector for finding, tracking and following up on B2B networking events for
**Borough Build** and **Been Ventures**. It serves a REST API and an MCP endpoint
so an AI agent host (Muse, Claude Desktop, VS Code) can use the same tools.

## What it does

- **Discover events** across NY, NJ, CT, MA, PA, DE and DC with Tavily web search.
  Results are unverified candidates; nothing is saved until you confirm one.
- **Track events** you plan to attend: `discovered`, `interested`, `registered`,
  `attended`, `skipped`, optionally tagged with the company attending.
- **Capture contacts** from business cards, voice notes and conversation summaries.
- **Draft follow-ups** per company. Drafts are never sent.
- **Score prospects** against Borough Build or Been Ventures (heuristic, 0-10).
- **Telegram reminders** for upcoming events, sent only when you confirm.
- **Company profiles and matching** (`/companies`, `/match`) for B2B partner lookup.

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
- `POST /contacts`, `GET /contacts`, `PATCH /contacts/{id}`, `POST /contacts/{id}/followup`
- `POST /compatibility`, `POST /reminders/telegram`
- `POST/GET/PATCH/DELETE /companies`, `POST /match`

Brand keys are `borough_build` and `been_ventures`. Edit their descriptions and
follow-up offerings in [app/brands.py](app/brands.py).

## MCP tools

`search_networking_events`, `discover_networking_event_candidates`,
`confirm_networking_event`, `update_networking_event`,
`process_muse_handsfree_context`, `list_networking_contacts`,
`update_networking_contact`, `match_credentials_compatibility`,
`generate_tailored_pitch_deck_or_followup`, `send_event_reminders_to_telegram`,
`send_report_to_telegram`.

Local (stdio) for VS Code or Claude Desktop:

```json
{
  "servers": {
    "networking-events": {
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

1. **New + → Blueprint**, pick this repo. Render reads `render.yaml`
   (service `networking-connector`) and generates `API_KEY` and `MCP_API_KEY`.
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
