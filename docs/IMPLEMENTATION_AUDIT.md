# Implementation Audit

## Verified findings (before changes)
- Framework: FastAPI (`app/main.py`), SQLAlchemy/SQLite (`leads.db`), MCP server (`app/mcp_server.py`, mounted at `/mcp`).
- No references to Rebirth API existed anywhere in the code, config, or docs.
- `OVERPASS_API_KEY` and `TELEGRAM_BOT_TOKEN` appeared only in the local `.env`; no code read them and nothing loaded `.env`.
- No HVAC business-search endpoint or Overpass client existed. `hvac` was only a `Trade` enum value for seeded leads/contractors.
- Geocoding: static 28-entry ZIP table in `app/geo.py`.
- Auth: `X-API-Key` (`DISPATCH_API_KEY`) guards mutating dispatch routes only; lead search and MCP are unauthenticated reads.
- `.env` is gitignored and untracked. There was no `.env.example` and no tests.

## Changes
- `app/overpass.py`: Overpass client, normalization, dedup, cache, retries.
- `app/routers/businesses.py`: `GET /businesses/hvac/search`.
- `app/mcp_server.py`: new `search_hvac_businesses` tool; existing tools untouched.
- `app/config.py`: `.env` loading, Overpass/Nominatim settings, `validate_settings()` (reports variable names only); `TELEGRAM_BOT_TOKEN` optional and unused by search.
- `.env.example`, `requirements.txt` (python-dotenv, httpx, pytest), `tests/test_hvac_search.py`.

## Notes
- `OVERPASS_API_KEY` is not used: the public Overpass API has no key. The `.env` entry can be removed.
- OSM coverage is incomplete; results are never nationwide-complete and never fabricated.

## Verification
- Automated: 17 mocked tests pass (`pytest`).
- Live smoke test (public Overpass, ZIP 10001, 10 mi): returned 5 real OSM records. The name-based query degraded with a warning (public-server load), so only tagged results were returned. Live retrieval verified once; coverage is not exhaustive.
- Rebirth: no code or config ever referenced it, so nothing needed removal.
