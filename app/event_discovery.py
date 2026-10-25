"""Event candidate discovery via Tavily web search.

Results are unverified web hits. Nothing is written to the curated events file
until `confirm_event` is called explicitly with details the user has checked.
"""
import json
import re
from datetime import date

import httpx

from app import networking
from app.config import settings

STATE_NAMES = {
    "NY": "New York", "NJ": "New Jersey", "CT": "Connecticut", "MA": "Massachusetts",
    "PA": "Pennsylvania", "DE": "Delaware", "DC": "Washington DC",
}
GROUP_TERMS = {
    "WMBE": "WMBE women minority business enterprise",
    "MWBE": "MWBE minority women-owned business expo procurement",
    "Muslim_Business": "Muslim business owners networking halal expo",
    "Supplier_Diversity": "supplier diversity minority supplier development council",
    "Tech_Contracting": "tech contractors small business technology networking",
}
EVENT_WORDS = re.compile(r"event|expo|summit|conference|webinar|networking|fair|forum|mixer|workshop", re.I)


class DiscoveryError(Exception):
    pass


def _search(query: str, max_results: int) -> list[dict]:
    if not settings.tavily_api_key:
        raise DiscoveryError("TAVILY_API_KEY is not set")
    try:
        response = httpx.post(
            settings.tavily_api_url,
            headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
            json={"query": query, "max_results": max_results, "search_depth": "basic"},
            timeout=30,
        )
    except httpx.HTTPError as exc:
        raise DiscoveryError(f"Tavily request failed: {type(exc).__name__}") from exc
    if response.status_code in {401, 403}:
        raise DiscoveryError("Tavily rejected the API key")
    if response.status_code == 429:
        raise DiscoveryError("Tavily rate limit or quota reached")
    if response.status_code >= 400:
        raise DiscoveryError(f"Tavily returned HTTP {response.status_code}")
    return response.json().get("results", [])


def discover_candidates(
    states: list[str],
    target_groups: list[str],
    event_format: str = "all",
    max_results: int = 10,
) -> dict:
    states_up = [s.upper() for s in states]
    if not states_up or not set(states_up) <= set(networking.DEFAULT_STATES):
        return {"error": f"states must be within {networking.DEFAULT_STATES}"}
    if not target_groups or not set(target_groups) <= networking.TARGET_GROUPS:
        return {"error": f"target_groups must be within {sorted(networking.TARGET_GROUPS)}"}
    if event_format not in networking.EVENT_FORMATS:
        return {"error": f"event_format must be one of {sorted(networking.EVENT_FORMATS)}"}
    max_results = max(1, min(max_results, 20))

    year = date.today().year
    fmt = "" if event_format == "all" else event_format.replace("_", " ")
    places = " OR ".join(STATE_NAMES[s] for s in states_up)
    seen: set[str] = set()
    candidates: list[dict] = []
    try:
        for group in target_groups:
            query = f"upcoming {GROUP_TERMS[group]} event {fmt} ({places}) {year} {year + 1}"
            for hit in _search(query, max_results):
                url = hit.get("url", "")
                if not url or url in seen:
                    continue
                seen.add(url)
                title = hit.get("title", "")
                snippet = (hit.get("content") or "")[:400]
                candidates.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "matched_group": group,
                    "looks_like_event": bool(EVENT_WORDS.search(f"{title} {snippet}")),
                    "status": "unverified",
                })
    except DiscoveryError as exc:
        return {"error": str(exc), "candidates": []}

    candidates.sort(key=lambda c: not c["looks_like_event"])
    return {
        "source": "tavily_web_search",
        "count": len(candidates),
        "candidates": candidates[: max_results * len(target_groups)],
        "note": "Unverified. Open each URL, confirm date/location, then call confirm_networking_event.",
    }


def confirm_event(
    title: str,
    event_date: str,
    state: str,
    event_format: str,
    organizer: str,
    target_groups: list[str],
    registration_url: str,
    location: str = "",
    time: str = "",
) -> dict:
    try:
        parsed = date.fromisoformat(event_date)
    except ValueError:
        return {"error": "event_date must be YYYY-MM-DD"}
    if state.upper() not in networking.DEFAULT_STATES:
        return {"error": f"state must be within {networking.DEFAULT_STATES}"}
    if event_format not in networking.EVENT_FORMATS - {"all"}:
        return {"error": "event_format must be in_person, virtual, or hybrid"}
    if not target_groups or not set(target_groups) <= networking.TARGET_GROUPS:
        return {"error": f"target_groups must be within {sorted(networking.TARGET_GROUPS)}"}
    if not registration_url.startswith(("http://", "https://")):
        return {"error": "registration_url must be an http(s) URL"}
    if not title.strip() or not organizer.strip():
        return {"error": "title and organizer are required"}

    events = networking._load_events()
    if any(e.get("registration_url") == registration_url and e.get("date") == event_date for e in events):
        return {"error": "Event already exists in the curated file"}

    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:40]
    event = {
        "event_id": f"evt_{parsed.isoformat()}_{slug}",
        "title": title.strip(),
        "date": event_date,
        "time": time,
        "state": state.upper(),
        "location": location,
        "format": event_format,
        "organizer": organizer.strip(),
        "target_groups": target_groups,
        "registration_url": registration_url,
    }
    events.append(event)
    networking.EVENTS_FILE.write_text(json.dumps(events, indent=2) + "\n", encoding="utf-8")
    return {"saved": event}
