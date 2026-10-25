from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db() -> Iterator[Session]:
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        client.headers.update({"X-API-Key": settings.api_key})
        yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def company_profile() -> dict:
    return {
        "company_name": "Atlas Tech Solutions",
        "legal_structure": "C-Corp",
        "certifications": ["MWBE", "WMBE"],
        "demographic_tags": ["Muslim-Owned", "Women-Owned", "Export-Ready"],
        "naics_code": "541511",
        "location": {"city": "Albany", "state": "NY", "country": "USA"},
        "contact_info": {
            "email": "contact@atlastech.example",
            "phone": "+1-518-555-0199",
            "website": "https://atlastech.example",
        },
        "target_global_markets": ["UAE", "UK", "USA"],
        "description": "Custom software development agency serving public sector clients",
        "capabilities": ["enterprise software integration"],
    }


def test_create_list_get_and_match_company_profile(client):
    assert client.get("/companies", headers={"X-API-Key": "wrong"}).status_code == 401
    created = client.post("/companies", json=company_profile())
    assert created.status_code == 201
    profile = created.json()
    assert profile["company_id"]
    assert profile["location"]["city"] == "Albany"
    assert profile["contact_info"]["email"] == "contact@atlastech.example"

    listed = client.get("/companies")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    retrieved = client.get(f"/companies/{profile['company_id']}")
    assert retrieved.status_code == 200
    assert retrieved.json()["company_name"] == "Atlas Tech Solutions"

    updated = client.patch(
        f"/companies/{profile['company_id']}",
        json={"description": "Custom software development and GCC market services"},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Custom software development and GCC market services"
    assert client.patch(
        f"/companies/{profile['company_id']}",
        json={"location": None},
    ).status_code == 422

    deleted = client.delete(f"/companies/{profile['company_id']}")
    assert deleted.status_code == 204
    assert client.get(f"/companies/{profile['company_id']}").status_code == 404
    assert client.get("/companies/not-a-company").status_code == 404

    recreated = client.post("/companies", json=company_profile()).json()
    matched = client.post("/match", params={"query": "custom software development"})
    assert matched.status_code == 200
    assert matched.json()["matches"][0]["company_id"] == recreated["company_id"]
    assert matched.json()["matches"][0]["score"] > 0.3
    assert "MWBE" in matched.json()["matches"][0]["tags"]


def test_match_threshold_and_explicit_notification(client, monkeypatch):
    client.post("/companies", json=company_profile())
    alerts = []
    monkeypatch.setattr(
        "app.routers.matchmaking.send_b2b_lead_alert",
        lambda company_name, tags, score: alerts.append((company_name, tags, score)),
    )

    no_notification = client.post("/match", params={"query": "custom software development"})
    assert no_notification.status_code == 200
    assert alerts == []

    response = client.post(
        "/match",
        params={"query": "custom software development", "notify": "true"},
    )
    assert response.status_code == 200
    assert len(alerts) == 1

    no_match = client.post("/match", params={"query": "unrelated gardening services"})
    assert no_match.status_code == 200
    assert no_match.json()["matches"] == []
    high_threshold = client.post(
        "/match",
        params={"query": "custom software development", "min_score": 1},
    )
    assert high_threshold.json()["matches"] == []
