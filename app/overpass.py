"""HVAC business discovery backed by the public OpenStreetMap Overpass API.

Results are real mapped OSM objects only; OSM coverage is incomplete, so an
empty list means "nothing mapped here", never "no HVAC companies exist".
"""
import re
import threading
import time
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.geo import LocationNotFoundError, haversine_miles, resolve_location

METERS_PER_MILE = 1609.344
MAX_RADIUS_MILES = 25
NAME_PATTERN = "hvac|heating|air.?condition|furnace|a/?c (repair|service)|climate control"

_cache: dict[tuple, tuple[float, list[dict]]] = {}
_cache_lock = threading.Lock()
_geocode_cache: dict[str, tuple[float, float]] = {}


class ProviderError(Exception):
    status_code = 502


class ProviderTimeout(ProviderError):
    status_code = 504


class ProviderRateLimited(ProviderError):
    status_code = 429

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class InvalidSearch(ValueError):
    pass


def clear_caches() -> None:
    with _cache_lock:
        _cache.clear()
    _geocode_cache.clear()


def _geocode_nominatim(location: str) -> tuple[float, float]:
    if location in _geocode_cache:
        return _geocode_cache[location]
    try:
        response = httpx.get(
            settings.nominatim_api_url,
            params={"q": location, "format": "jsonv2", "limit": 1, "countrycodes": "us"},
            headers={"User-Agent": settings.osm_user_agent},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ProviderError("The geocoding service is unavailable; try a supported ZIP code") from exc
    if not results:
        raise LocationNotFoundError(f"Unrecognized location: {location!r}")
    coords = (float(results[0]["lat"]), float(results[0]["lon"]))
    _geocode_cache[location] = coords
    return coords


def resolve_search_location(location: str) -> tuple[float, float]:
    cleaned = (location or "").strip()
    if not cleaned:
        raise InvalidSearch("A location (ZIP code or 'City, ST') is required")
    try:
        return resolve_location(cleaned)
    except LocationNotFoundError:
        # Without a geocoder, unknown ZIP/city values fail rather than guess.
        if not settings.nominatim_enabled:
            raise LocationNotFoundError(
                f"Unrecognized location: {location!r}. Only built-in ZIP codes and cities are "
                "supported unless NOMINATIM_ENABLED=true."
            ) from None
        if len(cleaned) > 120:
            raise InvalidSearch("Location is too long") from None
        return _geocode_nominatim(cleaned)


def build_queries(lat: float, lon: float, radius_miles: float, timeout: int) -> tuple[str, str]:
    """Tag-based query (primary) and a heavier name-based query (best effort)."""
    radius_m = int(radius_miles * METERS_PER_MILE)
    around = f"(around:{radius_m},{lat:.6f},{lon:.6f})"
    head = f"[out:json][timeout:{timeout}];\n(\n"
    tail = ");\nout center tags 200;"
    by_tag = "".join(f'  nwr["{key}"="hvac"]{around};\n' for key in ("craft", "shop", "office"))
    by_name = f'  nwr["name"~"{NAME_PATTERN}",i][~"^(shop|office|craft)$"~"."]{around};\n'
    return head + by_tag + tail, head + by_name + tail


def _retry_after(response: httpx.Response) -> int | None:
    value = response.headers.get("retry-after", "")
    return int(value) if value.isdigit() else None


def _fetch(query: str, retries: int | None = None) -> dict:
    attempts = (settings.overpass_max_retries if retries is None else retries) + 1
    last_error: ProviderError | None = None
    for attempt in range(attempts):
        try:
            response = httpx.post(
                settings.overpass_api_url,
                data={"data": query},
                headers={"User-Agent": settings.osm_user_agent},
                timeout=settings.overpass_timeout_seconds,
            )
        except httpx.TimeoutException:
            last_error = ProviderTimeout("The OpenStreetMap Overpass service timed out")
        except httpx.HTTPError:
            last_error = ProviderError("The OpenStreetMap Overpass service could not be reached")
        else:
            if response.status_code == 429:
                raise ProviderRateLimited(
                    "The OpenStreetMap Overpass service is rate limiting requests; try again shortly",
                    _retry_after(response),
                )
            if response.status_code == 504:
                last_error = ProviderTimeout("The OpenStreetMap Overpass service timed out")
            elif response.status_code >= 500:
                last_error = ProviderError(
                    f"The OpenStreetMap Overpass service returned HTTP {response.status_code}"
                )
            elif response.status_code >= 400:
                raise ProviderError(f"The OpenStreetMap Overpass service rejected the query (HTTP {response.status_code})")
            else:
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise ProviderError("The OpenStreetMap Overpass service returned an invalid response") from exc
                remark = str(payload.get("remark", ""))
                if "runtime error" in remark.lower() or "timed out" in remark.lower():
                    last_error = ProviderTimeout("The OpenStreetMap Overpass query did not complete")
                else:
                    return payload
        if attempt < attempts - 1:
            time.sleep(min(2 ** attempt, 4))
    assert last_error is not None
    raise last_error


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _normalize(element: dict, origin: tuple[float, float], retrieved_at: str) -> dict | None:
    tags = element.get("tags") or {}
    lat = element.get("lat", (element.get("center") or {}).get("lat"))
    lon = element.get("lon", (element.get("center") or {}).get("lon"))
    if lat is None or lon is None or element.get("type") not in {"node", "way", "relation"}:
        return None

    street = " ".join(p for p in (tags.get("addr:housenumber"), tags.get("addr:street")) if p) or None
    osm_type, osm_id = element["type"], element["id"]
    return {
        "business_name": _clean(tags.get("name")) or _clean(tags.get("operator")) or _clean(tags.get("brand")),
        "trade": "hvac",
        "address": street,
        "city": _clean(tags.get("addr:city")),
        "state": _clean(tags.get("addr:state")),
        "zip_code": _clean(tags.get("addr:postcode")),
        "latitude": lat,
        "longitude": lon,
        "website": _clean(tags.get("website") or tags.get("contact:website")),
        "phone": _clean(tags.get("phone") or tags.get("contact:phone")),
        "distance_miles": round(haversine_miles(origin[0], origin[1], lat, lon), 2),
        "osm_type": osm_type,
        "osm_id": osm_id,
        "source": "openstreetmap_overpass",
        "source_url": f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
        "retrieved_at": retrieved_at,
    }


def _fallback_key(record: dict) -> tuple | None:
    if not record["business_name"]:
        return None
    name = re.sub(r"[^a-z0-9]", "", record["business_name"].lower())
    return name, round(record["latitude"], 3), round(record["longitude"], 3)


def dedupe(records: list[dict]) -> list[dict]:
    seen_ids: set[tuple] = set()
    seen_fallback: set[tuple] = set()
    unique: list[dict] = []
    for record in records:
        identity = (record["osm_type"], record["osm_id"])
        fallback = _fallback_key(record)
        if identity in seen_ids or (fallback and fallback in seen_fallback):
            continue
        seen_ids.add(identity)
        if fallback:
            seen_fallback.add(fallback)
        unique.append(record)
    return unique


def search_hvac_businesses(location: str, radius_miles: float = 15, limit: int | None = None) -> dict:
    if not 0 < radius_miles <= MAX_RADIUS_MILES:
        raise InvalidSearch(f"radius_miles must be greater than 0 and at most {MAX_RADIUS_MILES}")
    limit = min(limit or settings.max_search_results, settings.max_search_results)

    lat, lon = resolve_search_location(location)
    cache_key = (round(lat, 3), round(lon, 3), radius_miles)
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(cache_key)
    warnings: list[str] = []
    if cached and now - cached[0] < settings.overpass_cache_ttl_seconds:
        records, retrieved_at = cached[1]
    else:
        timeout = max(1, int(settings.overpass_timeout_seconds) - 5)
        tag_query, name_query = build_queries(lat, lon, radius_miles, timeout)
        elements = _fetch(tag_query).get("elements", [])
        try:
            elements += _fetch(name_query, retries=0).get("elements", [])
        except ProviderError:
            warnings.append("Name-based matching was unavailable; only tagged HVAC businesses are shown")
        retrieved_at = datetime.now(timezone.utc).isoformat()
        records = [
            record for element in elements if (record := _normalize(element, (lat, lon), retrieved_at))
        ]
        records = sorted(dedupe(records), key=lambda r: r["distance_miles"])
        # Partial results are not cached so the next request retries name matching.
        if not warnings:
            with _cache_lock:
                _cache[cache_key] = (now, (records, retrieved_at))

    return {
        "source": "openstreetmap_overpass",
        "is_test_fixture": False,
        "query": {"location": location, "radius_miles": radius_miles, "trade": "hvac"},
        "retrieved_at": retrieved_at,
        "warnings": warnings,
        "count": min(len(records), limit),
        "results": records[:limit],
        "disclaimer": (
            "Results are businesses mapped in OpenStreetMap and are not a complete list of "
            "HVAC companies; missing contact details are null."
        ),
    }
