import httpx

from app import event_discovery
from app.config import settings


def test_discover_candidates_uses_tavily_api_key(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "test-api-key")
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "NYC AI Business Networking Mixer",
                        "url": "https://events.example/ai-mixer",
                        "content": "A networking event for AI founders in New York.",
                    }
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(event_discovery.httpx, "post", fake_post)

    result = event_discovery.discover_candidates(
        ["NY"],
        ["Tech_Contracting"],
        max_results=2,
    )

    assert result["source"] == "tavily_web_search"
    assert result["count"] == 1
    assert result["candidates"][0]["status"] == "unverified"
    assert result["candidates"][0]["looks_like_event"] is True
    assert calls[0][1]["headers"]["Authorization"] == "Bearer test-api-key"
    assert "upcoming" in calls[0][1]["json"]["query"]


def test_discover_candidates_reports_missing_key_without_request(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", None)

    result = event_discovery.discover_candidates(["NY"], ["MWBE"])

    assert result == {"error": "TAVILY_API_KEY is not set", "candidates": []}


def test_discover_candidates_reports_rejected_key(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "invalid-key")

    def fake_post(url, **kwargs):
        return httpx.Response(401, request=httpx.Request("POST", url))

    monkeypatch.setattr(event_discovery.httpx, "post", fake_post)

    result = event_discovery.discover_candidates(["NY"], ["MWBE"])

    assert result == {"error": "Tavily rejected the API key", "candidates": []}


def test_discover_candidates_defaults_to_northeast_nightlife(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "test-api-key")
    queries = []

    def fake_post(url, **kwargs):
        queries.append(kwargs["json"]["query"])
        return httpx.Response(
            200,
            json={"results": []},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(event_discovery.httpx, "post", fake_post)

    result = event_discovery.discover_candidates()

    assert result["count"] == 0
    assert result["candidates"] == []
    assert len(queries) == 1
    assert "hip-hop" in queries[0]
    assert all(place in queries[0] for place in ("New York", "New Jersey", "Connecticut", "Massachusetts"))


def test_nightlife_results_are_recognized_as_events(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "test-api-key")

    def fake_post(url, **kwargs):
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Friday Hip-Hop Party",
                        "url": "https://events.example/friday-party",
                        "content": "Live DJs and dancing.",
                    }
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(event_discovery.httpx, "post", fake_post)

    result = event_discovery.discover_candidates(["NY"], ["Hip_Hop"])

    assert result["candidates"][0]["matched_group"] == "Hip_Hop"
    assert result["candidates"][0]["looks_like_event"] is True
