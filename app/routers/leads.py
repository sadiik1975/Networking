from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud
from app.config import settings
from app.database import get_db
from app.geo import LocationNotFoundError
from app.models_db import Trade
from app.schemas import ErrorResponse, LeadDetail, LeadSummary

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get(
    "/search",
    response_model=list[LeadSummary],
    summary="Search verified local project leads by trade and geographic radius",
    responses={400: {"model": ErrorResponse}},
)
def search_leads(
    trade: Trade = Query(..., description="Trade category to filter by"),
    location: str | None = Query(None, description="ZIP code or 'City, ST' to search around"),
    zip_code: str | None = Query(None, min_length=5, max_length=5, description="Origin ZIP code"),
    radius_miles: int = Query(100, gt=0, le=500, description="Maximum search radius in miles"),
    min_radius: int | None = Query(None, gt=0, le=500, description="Compatibility alias for radius_miles"),
    min_value: float | None = Query(None, ge=0, description="Minimum estimated project value"),
    ownership_filter: str | None = Query(None, description="Exact ownership category, e.g. Minority-Owned"),
    db: Session = Depends(get_db),
) -> list[LeadSummary]:
    search_location = zip_code or location
    if not search_location:
        raise HTTPException(status_code=422, detail="Provide either zip_code or location")

    try:
        matches = crud.search_leads(
            db=db,
            trade=trade,
            location=search_location,
            radius_miles=min_radius or radius_miles,
            min_value=min_value,
            ownership_filter=ownership_filter,
            max_results=settings.max_search_results,
        )
    except LocationNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return [
        LeadSummary(
            id=lead.id,
            trade=lead.trade,
            project_type=lead.project_type,
            description=lead.description,
            city=lead.city,
            state=lead.state,
            zip_code=lead.zip_code,
            distance_miles=round(distance, 2),
            estimated_value=lead.estimated_value,
            issue_date=lead.issue_date,
            project_scale=lead.project_scale,
            municipal_source_url=lead.municipal_source_url,
            ownership_category=lead.ownership_category,
            certification_details=lead.certification_details,
            source_url=lead.source_url,
        )
        for lead, distance in matches
    ]


@router.get(
    "/{lead_id}",
    response_model=LeadDetail,
    summary="Retrieve deep-dive specifications for a specific lead",
    responses={404: {"model": ErrorResponse}},
)
def get_lead(lead_id: str, db: Session = Depends(get_db)) -> LeadDetail:
    lead = crud.get_lead(db, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id!r} not found")
    return LeadDetail.model_validate(lead)
