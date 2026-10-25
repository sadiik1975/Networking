from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app import overpass
from app.geo import LocationNotFoundError

router = APIRouter(tags=["businesses"])


class BusinessRecord(BaseModel):
    business_name: str | None = None
    trade: str
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    latitude: float
    longitude: float
    website: str | None = None
    phone: str | None = None
    distance_miles: float
    osm_type: str
    osm_id: int
    source: str
    source_url: str
    retrieved_at: str


class BusinessSearchResponse(BaseModel):
    source: str
    is_test_fixture: bool
    query: dict
    retrieved_at: str
    warnings: list[str] = []
    count: int
    results: list[BusinessRecord]
    disclaimer: str


@router.get(
    "/businesses/hvac/search",
    response_model=BusinessSearchResponse,
    summary="Search mapped HVAC businesses (OpenStreetMap)",
)
def search_hvac_businesses(
    location: str = Query(..., min_length=1, max_length=120, description="ZIP code or 'City, ST'"),
    radius_miles: float = Query(15, gt=0, le=overpass.MAX_RADIUS_MILES),
    limit: int = Query(50, ge=1, le=200),
):
    try:
        return overpass.search_hvac_businesses(location, radius_miles, limit)
    except (LocationNotFoundError, overpass.InvalidSearch) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except overpass.ProviderRateLimited as exc:
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        raise HTTPException(status_code=429, detail=str(exc), headers=headers) from exc
    except overpass.ProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
