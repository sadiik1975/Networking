from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.company_models import CompanyProfile
from app.database import get_db
from app.matchmaking import find_matches
from app.notifier import NotificationNotConfigured, NotificationError, send_b2b_lead_alert
from app.schemas import (
    CompanyProfileCreate,
    CompanyProfileResponse,
    CompanyProfileUpdate,
    MatchResponse,
)

router = APIRouter(tags=["matchmaking"])


@router.post(
    "/companies",
    response_model=CompanyProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a business profile for matchmaking",
    dependencies=[Depends(require_api_key)],
)
def create_company_profile(
    profile: CompanyProfileCreate,
    db: Session = Depends(get_db),
) -> CompanyProfileResponse:
    company = CompanyProfile(
        company_id=str(uuid4()),
        **profile.model_dump(mode="json"),
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return CompanyProfileResponse.model_validate(company)


@router.get(
    "/companies",
    response_model=list[CompanyProfileResponse],
    summary="List business profiles",
    dependencies=[Depends(require_api_key)],
)
def list_company_profiles(db: Session = Depends(get_db)) -> list[CompanyProfileResponse]:
    companies = db.query(CompanyProfile).order_by(CompanyProfile.company_name).all()
    return [CompanyProfileResponse.model_validate(company) for company in companies]


@router.get(
    "/companies/{company_id}",
    response_model=CompanyProfileResponse,
    summary="Get a business profile",
    dependencies=[Depends(require_api_key)],
)
def get_company_profile(company_id: str, db: Session = Depends(get_db)) -> CompanyProfileResponse:
    company = db.get(CompanyProfile, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company profile not found")
    return CompanyProfileResponse.model_validate(company)


@router.patch(
    "/companies/{company_id}",
    response_model=CompanyProfileResponse,
    summary="Update a business profile",
    dependencies=[Depends(require_api_key)],
)
def update_company_profile(
    company_id: str,
    profile: CompanyProfileUpdate,
    db: Session = Depends(get_db),
) -> CompanyProfileResponse:
    company = db.get(CompanyProfile, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company profile not found")
    for field, value in profile.model_dump(mode="json", exclude_unset=True).items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    return CompanyProfileResponse.model_validate(company)


@router.delete(
    "/companies/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a business profile",
    dependencies=[Depends(require_api_key)],
)
def delete_company_profile(company_id: str, db: Session = Depends(get_db)) -> Response:
    company = db.get(CompanyProfile, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company profile not found")
    db.delete(company)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/match",
    response_model=MatchResponse,
    summary="Match a business intent to company profiles",
    dependencies=[Depends(require_api_key)],
)
def match_business(
    query: str = Query(..., min_length=1, max_length=2000),
    min_score: float = Query(0.3, ge=0, le=1),
    notify: bool = Query(False, description="Send Telegram alerts for matches; requires explicit opt-in"),
    db: Session = Depends(get_db),
) -> MatchResponse:
    matches = find_matches(query.strip(), db.query(CompanyProfile).all(), min_score)

    if notify and matches:
        try:
            for match in matches:
                send_b2b_lead_alert(match.company.company_name, match.tags, match.score)
        except NotificationNotConfigured as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except NotificationError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return MatchResponse(
        query=query,
        matches=[
            {
                "company": match.company.company_name,
                "company_id": match.company.company_id,
                "score": match.score,
                "tags": match.tags,
            }
            for match in matches
        ],
    )
