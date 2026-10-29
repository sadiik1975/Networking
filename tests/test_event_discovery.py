import httpx

from app import event_discovery
from app.config import settings


def _patch_client_post(monkeypatch, fake_post):
    """Patch the httpx.Client.post the discovery code actually calls."""
    monkeypatch.setattr(httpx.Client, "post", fake_post)


def test_discover_candidates_uses_tavily_api_key(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "test-api-key")
    calls = []

    def fake_post(self, url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "NYC AI Business Networking Event",
                        "url": "https://events.example/ai-networking",
                        "content": "A networking event for AI founders in New York.",
                    }
                ]
            },
            request=httpx.Request("POST", url),
        )

    _patch_client_post(monkeypatch, fake_post)

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

    def fake_post(self, url, **kwargs):
        return httpx.Response(401, request=httpx.Request("POST", url))

    _patch_client_post(monkeypatch, fake_post)

    result = event_discovery.discover_candidates(["NY"], ["MWBE"])

    assert result == {"error": "Tavily rejected the API key", "candidates": []}


def test_discover_candidates_defaults_to_northeast_business(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "test-api-key")
    queries = []

    def fake_post(self, url, **kwargs):
        queries.append(kwargs["json"]["query"])
        return httpx.Response(
            200,
            json={"results": []},
            request=httpx.Request("POST", url),
        )

    _patch_client_post(monkeypatch, fake_post)

    result = event_discovery.discover_candidates()

    assert result["count"] == 0
    assert result["candidates"] == []
    assert len(queries) == 3
    assert "MWBE" in queries[0]
    assert all(
        place in query
        for query in queries
        for place in ("New York", "New Jersey", "Connecticut", "Massachusetts")
    )


def test_business_results_are_recognized_as_events(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "test-api-key")

    def fake_post(self, url, **kwargs):
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Albany MWBE Procurement Forum",
                        "url": "https://events.example/mwbe-forum",
                        "content": "Business networking, supplier diversity and buyer matchmaking.",
                    }
                ]
            },
            request=httpx.Request("POST", url),
        )

    _patch_client_post(monkeypatch, fake_post)

    result = event_discovery.discover_candidates(["NY"], ["MWBE"])

    assert result["candidates"][0]["matched_group"] == "MWBE"
    assert result["candidates"][0]["looks_like_event"] is True
