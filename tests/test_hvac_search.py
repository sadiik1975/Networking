import httpx
import pytest
from fastapi.testclient import TestClient

from app import overpass
from app.config import settings, validate_settings
from app.main import app

client = TestClient(app)


def node(osm_id, name="Cool Air HVAC", lat=40.75, lon=-73.99, **tags):
    return {"type": "node", "id": osm_id, "lat": lat, "lon": lon, "tags": {"name": name, "craft": "hvac", **tags}}


def mock_post(monkeypatch, payload=None, status=200, exc=None, headers=None):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        if exc:
            raise exc
        return httpx.Response(status, json=payload if payload is not None else {"elements": []},
                              headers=headers, request=httpx.Request("POST", url))

    monkeypatch.setattr(overpass.httpx, "post", fake_post)
    return calls


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    overpass.clear_caches()
    monkeypatch.setattr(overpass.time, "sleep", lambda _: None)
    monkeypatch.setattr(settings, "nominatim_enabled", False)
    yield
    overpass.clear_caches()


def search(location="10001", **params):
    return client.get("/businesses/hvac/search", params={"location": location, **params})


def test_success_normalizes_fields(monkeypatch):
    calls = mock_post(monkeypatch, {"elements": [node(
        1, **{"addr:housenumber": "5", "addr:street": "Main St", "addr:city": "New York",
              "addr:postcode": "10001", "contact:phone": "+1 212 555 0100", "website": "https://x.test"})]})
    body = search().json()
    rec = body["results"][0]
    assert body["source"] == "openstreetmap_overpass" and body["is_test_fixture"] is False
    assert rec["business_name"] == "Cool Air HVAC" and rec["address"] == "5 Main St"
    assert rec["zip_code"] == "10001" and rec["phone"] == "+1 212 555 0100"
    assert rec["source_url"] == "https://www.openstreetmap.org/node/1" and rec["retrieved_at"]
    assert calls[0][0] == settings.overpass_api_url
    assert 'nwr["craft"="hvac"]' in calls[0][1]["data"]["data"]


def test_empty_results_are_honest(monkeypatch):
    mock_post(monkeypatch, {"elements": []})
    body = search().json()
    assert body["count"] == 0 and body["results"] == []


def test_missing_name_and_contacts_are_null(monkeypatch):
    mock_post(monkeypatch, {"elements": [{"type": "way", "id": 9, "center": {"lat": 40.75, "lon": -73.99},
                                          "tags": {"craft": "hvac"}}]})
    rec = search().json()["results"][0]
    assert rec["business_name"] is None and rec["phone"] is None and rec["website"] is None
    assert rec["osm_type"] == "way"


def test_elements_without_coordinates_skipped(monkeypatch):
    mock_post(monkeypatch, {"elements": [{"type": "relation", "id": 3, "tags": {"name": "X"}}]})
    assert search().json()["count"] == 0


def test_invalid_location_and_radius():
    assert search("Nowhereville, ZZ").status_code == 400
    assert search("   ").status_code == 400
    assert search(radius_miles=500).status_code == 422


def test_zip_and_city_resolve(monkeypatch):
    mock_post(monkeypatch)
    assert search("60601").status_code == 200
    assert search("Chicago, IL").status_code == 200


def test_duplicates_removed(monkeypatch):
    mock_post(monkeypatch, {"elements": [node(1), node(1), node(2, name="cool air hvac!")]})
    assert search().json()["count"] == 1


def test_timeout_retries_then_504(monkeypatch):
    calls = mock_post(monkeypatch, exc=httpx.ReadTimeout("slow"))
    response = search()
    assert response.status_code == 504 and len(calls) == settings.overpass_max_retries + 1


def test_unavailable_502(monkeypatch):
    mock_post(monkeypatch, status=503)
    assert search().status_code == 502
    mock_post(monkeypatch, exc=httpx.ConnectError("down"))
    assert search("60601").status_code == 502


def test_rate_limit_429_not_retried(monkeypatch):
    calls = mock_post(monkeypatch, status=429, headers={"retry-after": "12"})
    response = search()
    assert response.status_code == 429 and response.headers["retry-after"] == "12" and len(calls) == 1


def test_overpass_runtime_remark_is_error(monkeypatch):
    mock_post(monkeypatch, {"elements": [], "remark": "runtime error: Query timed out"})
    assert search().status_code == 504


def test_cache_avoids_second_call(monkeypatch):
    calls = mock_post(monkeypatch, {"elements": [node(1)]})
    search()
    search()
    assert len(calls) == 2  # tag + name query, once


def test_no_api_key_needed(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", None)
    calls = mock_post(monkeypatch)
    assert search().status_code == 200
    assert "authorization" not in {k.lower() for k in calls[0][1]["headers"]}
    assert "User-Agent" in calls[0][1]["headers"]


def test_validate_settings_reports_names_only(monkeypatch):
    monkeypatch.setattr(settings, "overpass_api_url", "not a url")
    assert validate_settings() == ["OVERPASS_API_URL must be an http(s) URL"]


def test_existing_routes_and_auth_unchanged():
    assert client.get("/health").json()["status"] == "ok"
    leads = client.get("/leads/search", params={"trade": "hvac", "location": "10001"})
    assert leads.status_code == 200
    assert client.post("/contractors", json={}).status_code == 401
    assert client.post("/contractors", json={}, headers={"X-API-Key": "wrong"}).status_code == 401
    ok = client.post("/contractors", json={}, headers={"X-API-Key": settings.dispatch_api_key})
    assert ok.status_code == 422


def test_mcp_tool_returns_error_not_fixture(monkeypatch):
    from app.mcp_server import search_hvac_businesses

    mock_post(monkeypatch, status=503)
    result = search_hvac_businesses("10001")
    assert "error" in result and result["results"] == []


def test_name_query_failure_degrades_with_warning(monkeypatch):
    def fake_post(url, **kwargs):
        if "\"craft\"=\"hvac\"" in kwargs["data"]["data"]:
            return httpx.Response(200, json={"elements": [node(1)]}, request=httpx.Request("POST", url))
        return httpx.Response(504, request=httpx.Request("POST", url))

    monkeypatch.setattr(overpass.httpx, "post", fake_post)
    body = search().json()
    assert body["count"] == 1 and body["warnings"]
