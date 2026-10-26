"""Event candidate discovery via Tavily web search. (https://raw.githubusercontent.com/sadiik1975/Networking/main/app/event_discovery.py)

Results are unverified web hits. Nothing is saved until add_event is called
explicitly with details the user has checked.
"""

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
    "Nightlife": "hip-hop R&B Latin reggaeton Afrobeats nightlife lounges parties concerts DJs",
    "Hip_Hop": "hip-hop rap nightlife party concert DJ",
    "R_and_B": "R&B nightlife live music concert party",
    "Latin": "Latin music nightlife reggaeton salsa bachata party",
    "Afrobeats": "Afrobeats nightlife party concert DJ",
    "Live_Music": "live music nightlife concert show",
    "Lounges": "lounge nightlife events DJ live music",
    "Concerts": "hip-hop R&B Latin music concert",
    "Parties": "hip-hop Latin R&B party nightlife DJ",
    "B2B_Networking": "B2B business networking mixer",
    "Small_Business": "small business owners networking expo",
    "Startup_Tech": "startup founders technology AI networking meetup",
    "Chamber_of_Commerce": "chamber of commerce business after hours networking",
    "WMBE": "WMBE women minority business enterprise",
    "MWBE": "MWBE minority women-owned business expo procurement",
    "Muslim_Business": "Muslim business owners networking halal expo",
    "Supplier_Diversity": "supplier diversity minority supplier development council",
    "Tech_Contracting": "tech contractors small business technology networking",
}
EVENT_WORDS = re.compile(
    r"event|expo|summit|conference|webinar|networking|fair|forum|mixer|workshop|meetup|"
    r"nightlife|party|parties|lounge|club|concert|live music|DJ|festival|show",
    re.I,
)


class DiscoveryError(Exception):
    pass


def _search(query: str, max_results: int) -> list[dict]:
    api_key = (settings.tavily_api_key or "").strip()
    if not api_key:
        raise DiscoveryError("TAVILY_API_KEY is not set")
    api_url = (settings.tavily_api_url or "").strip()
    if not api_url.startswith("http"):
        api_url = "https://api.tavily.com/search"
    try:
        # trust_env=False: never let platform proxy variables break the request.
        with httpx.Client(trust_env=False, timeout=30) as client:
            response = client.post(
                api_url,
                headers={"Authorization": f"Bearer {api_key}"},
                json={"query": query, "max_results": max_results, "search_depth": "basic"},
            )
    except httpx.HTTPError as exc:
        raise DiscoveryError(f"Tavily request failed: {type(exc).__name__}: {exc}") from exc
    if response.status_code in {401, 403}:
        raise DiscoveryError("Tavily rejected the API key")
    if response.status_code == 429:
        raise DiscoveryError("Tavily rate limit or quota reached")
    if response.status_code >= 400:
        raise DiscoveryError(f"Tavily returned HTTP {response.status_code}")
    return response.json().get("results", [])


def discover_candidates(
    states: list[str] | None = None,
    target_groups: list[str] | None = None,
    event_format: str = "all",
    max_results: int = 10,
) -> dict:
    states_up = [s.upper() for s in (states or networking.DEFAULT_STATES)]
    groups = target_groups or ["Nightlife"]
    if not set(states_up) <= set(networking.SUPPORTED_STATES):
        return {"error": f"states must be within {networking.SUPPORTED_STATES}"}
    if not set(groups) <= networking.TARGET_GROUPS:
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
        for group in groups:
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
        "candidates": candidates[: max_results * len(groups)],
        "note": "Unverified. Open each URL, confirm date/location, then save with confirm_networking_event.",
    }
