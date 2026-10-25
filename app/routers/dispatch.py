from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app import crud
from app.auth import require_api_key
from app.database import get_db
from app.dispatch_models import (
    Contractor,
    Crew,
    Outreach,
    OutreachStatus,
    StatusEvent,
    WorkOrder,
    WorkOrderStatus,
)
from app.dispatch_schemas import (
    ContractorCreate,
    ContractorMatch,
    ContractorResponse,
    ContractorUpdate,
    CrewCreate,
    CrewResponse,
    OutreachCreate,
    OutreachResponse,
    ScheduleCreate,
    StatusEventResponse,
    StatusUpdate,
    WorkOrderResponse,
)
from app.geo import LocationNotFoundError, haversine_miles, resolve_location
from app.models_db import Lead, Trade

router = APIRouter(tags=["dispatch"])


def _contractor_response(contractor: Contractor, distance: float | None = None, score: float | None = None):
    data = ContractorResponse.model_validate(contractor).model_dump()
    if distance is not None:
        data["distance_miles"] = round(distance, 2)
    if score is not None:
        data["match_score"] = round(score, 2)
    return data


def _find_matches(
    db: Session,
    trade: Trade,
    zip_code: str,
    radius_miles: int,
    ownership_filter: str | None,
) -> list[dict]:
    try:
        origin_lat, origin_lon = resolve_location(zip_code)
    except LocationNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    contractors = db.execute(select(Contractor).where(Contractor.active.is_(True))).scalars().all()
    matches: list[dict] = []
    for contractor in contractors:
        if trade.value not in contractor.trades:
            continue
        if ownership_filter and contractor.ownership_category.lower() != ownership_filter.strip().lower():
            continue
        distance = haversine_miles(origin_lat, origin_lon, contractor.latitude, contractor.longitude)
        effective_radius = min(radius_miles, contractor.service_radius_miles)
        if distance > effective_radius:
            continue

        score = 50.0
        score += max(0.0, 30.0 * (1 - distance / max(radius_miles, 1)))
        score += 10.0 if contractor.verified else 0.0
        score += 10.0 if contractor.license_number and contractor.insurance_expiry else 0.0
        matches.append(_contractor_response(contractor, distance, score))

    return sorted(matches, key=lambda match: (-match["match_score"], match["distance_miles"]))


@router.post("/contractors", response_model=ContractorResponse, status_code=201, dependencies=[Depends(require_api_key)])
def create_contractor(payload: ContractorCreate, db: Session = Depends(get_db)) -> ContractorResponse:
    try:
        latitude, longitude = resolve_location(payload.service_zip)
    except LocationNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    contractor = Contractor(
        id=f"CON-{uuid4().hex[:10].upper()}",
        business_name=payload.business_name,
        email=str(payload.email),
        phone=payload.phone,
        trades=[trade.value for trade in payload.trades],
        service_zip=payload.service_zip,
        latitude=latitude,
        longitude=longitude,
        service_radius_miles=payload.service_radius_miles,
        ownership_category=payload.ownership_category,
        certification_details=payload.certification_details,
        source_url=str(payload.source_url) if payload.source_url else "",
        license_number=payload.license_number,
        license_state=payload.license_state.upper() if payload.license_state else None,
        insurance_expiry=payload.insurance_expiry,
    )
    db.add(contractor)
    db.commit()
    db.refresh(contractor)
    return ContractorResponse.model_validate(contractor)


@router.get("/contractors", response_model=list[ContractorResponse], dependencies=[Depends(require_api_key)])
def list_contractors(db: Session = Depends(get_db)) -> list[ContractorResponse]:
    contractors = db.execute(select(Contractor).order_by(Contractor.business_name)).scalars().all()
    return [ContractorResponse.model_validate(contractor) for contractor in contractors]


@router.post("/contractors/{contractor_id}/crews", response_model=CrewResponse, status_code=201, dependencies=[Depends(require_api_key)])
def create_crew(
    contractor_id: str,
    payload: CrewCreate,
    db: Session = Depends(get_db),
) -> CrewResponse:
    if db.get(Contractor, contractor_id) is None:
        raise HTTPException(status_code=404, detail="Contractor not found")
    crew = Crew(
        id=f"CREW-{uuid4().hex[:10].upper()}",
        contractor_id=contractor_id,
        name=payload.name,
        trade=payload.trade.value,
        capacity=payload.capacity,
    )
    db.add(crew)
    db.commit()
    db.refresh(crew)
    return CrewResponse.model_validate(crew)


@router.get("/contractors/search", response_model=list[ContractorMatch], dependencies=[Depends(require_api_key)])
def search_contractors(
    trade: Trade,
    zip_code: str = Query(..., min_length=5, max_length=5),
    radius_miles: int = Query(100, gt=0, le=500),
    ownership_filter: str | None = None,
    db: Session = Depends(get_db),
) -> list[ContractorMatch]:
    return [ContractorMatch.model_validate(match) for match in _find_matches(db, trade, zip_code, radius_miles, ownership_filter)]


@router.patch("/contractors/{contractor_id}", response_model=ContractorResponse, dependencies=[Depends(require_api_key)])
def update_contractor(
    contractor_id: str,
    payload: ContractorUpdate,
    db: Session = Depends(get_db),
) -> ContractorResponse:
    contractor = db.get(Contractor, contractor_id)
    if contractor is None:
        raise HTTPException(status_code=404, detail="Contractor not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "source_url":
            value = str(value)
        if field == "license_state" and value:
            value = value.upper()
        setattr(contractor, field, value)
    db.commit()
    db.refresh(contractor)
    return ContractorResponse.model_validate(contractor)


@router.delete("/contractors/{contractor_id}", response_model=ContractorResponse, dependencies=[Depends(require_api_key)])
def deactivate_contractor(contractor_id: str, db: Session = Depends(get_db)) -> ContractorResponse:
    contractor = db.get(Contractor, contractor_id)
    if contractor is None:
        raise HTTPException(status_code=404, detail="Contractor not found")
    contractor.active = False
    db.commit()
    db.refresh(contractor)
    return ContractorResponse.model_validate(contractor)


@router.get("/contractors/{contractor_id}", response_model=ContractorResponse, dependencies=[Depends(require_api_key)])
def get_contractor(contractor_id: str, db: Session = Depends(get_db)) -> ContractorResponse:
    contractor = db.get(Contractor, contractor_id)
    if contractor is None:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return ContractorResponse.model_validate(contractor)


@router.get("/leads/{lead_id}/matches", response_model=list[ContractorMatch], dependencies=[Depends(require_api_key)])
def match_contractors(
    lead_id: str,
    radius_miles: int = Query(100, gt=0, le=500),
    ownership_filter: str | None = None,
    db: Session = Depends(get_db),
) -> list[ContractorMatch]:
    lead = crud.get_lead(db, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return [ContractorMatch.model_validate(match) for match in _find_matches(db, lead.trade, lead.zip_code, radius_miles, ownership_filter)]


@router.post("/outreach/contact", response_model=OutreachResponse, status_code=201, dependencies=[Depends(require_api_key)])
def contact_contractor(payload: OutreachCreate, db: Session = Depends(get_db)) -> OutreachResponse:
    if not payload.confirmed:
        raise HTTPException(status_code=409, detail="Explicit confirmation is required before outreach is queued")
    if crud.get_lead(db, payload.lead_id) is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    if db.get(Contractor, payload.contractor_id) is None:
        raise HTTPException(status_code=404, detail="Contractor not found")

    outreach = Outreach(
        id=f"OUT-{uuid4().hex[:10].upper()}",
        lead_id=payload.lead_id,
        contractor_id=payload.contractor_id,
        channel=payload.channel,
        status=OutreachStatus.QUEUED,
        message=payload.message,
    )
    db.add(outreach)
    db.commit()
    db.refresh(outreach)
    return OutreachResponse.model_validate(outreach)


@router.post("/dispatch/schedule", response_model=WorkOrderResponse, status_code=201, dependencies=[Depends(require_api_key)])
def schedule_dispatch(payload: ScheduleCreate, db: Session = Depends(get_db)) -> WorkOrderResponse:
    if not payload.confirmed or not payload.customer_confirmed:
        raise HTTPException(status_code=409, detail="Dispatch and customer confirmation are both required")
    if payload.scheduled_end <= payload.scheduled_start:
        raise HTTPException(status_code=422, detail="scheduled_end must be after scheduled_start")

    if crud.get_lead(db, payload.lead_id) is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    contractor = db.get(Contractor, payload.contractor_id)
    crew = db.get(Crew, payload.crew_id)
    if contractor is None or crew is None or crew.contractor_id != contractor.id or not crew.active:
        raise HTTPException(status_code=404, detail="Active crew and contractor relationship not found")

    conflict = db.execute(
        select(WorkOrder).where(
            and_(
                WorkOrder.crew_id == crew.id,
                WorkOrder.status.not_in([WorkOrderStatus.CANCELLED, WorkOrderStatus.COMPLETED]),
                WorkOrder.scheduled_start < payload.scheduled_end,
                WorkOrder.scheduled_end > payload.scheduled_start,
            )
        )
    ).scalar_one_or_none()
    if conflict is not None:
        raise HTTPException(status_code=409, detail=f"Crew is already scheduled in work order {conflict.id}")

    work_order = WorkOrder(
        id=f"WO-{uuid4().hex[:10].upper()}",
        lead_id=payload.lead_id,
        contractor_id=payload.contractor_id,
        crew_id=payload.crew_id,
        status=WorkOrderStatus.SCHEDULED,
        scope=payload.scope,
        budget=payload.budget,
        scheduled_start=payload.scheduled_start,
        scheduled_end=payload.scheduled_end,
        customer_confirmed=True,
    )
    db.add(work_order)
    db.flush()
    db.add(StatusEvent(
        id=f"EVT-{uuid4().hex[:10].upper()}",
        work_order_id=work_order.id,
        from_status=None,
        to_status=WorkOrderStatus.SCHEDULED.value,
        actor="dispatch_api",
        note="Created after explicit customer and dispatch confirmation",
    ))
    db.commit()
    db.refresh(work_order)
    return WorkOrderResponse.model_validate(work_order)


_ALLOWED_TRANSITIONS: dict[WorkOrderStatus, set[WorkOrderStatus]] = {
    WorkOrderStatus.NEW: {WorkOrderStatus.CONTACTED, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.CONTACTED: {WorkOrderStatus.INTERESTED, WorkOrderStatus.ASSIGNED, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.INTERESTED: {WorkOrderStatus.ASSIGNED, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.ASSIGNED: {WorkOrderStatus.SCHEDULED, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.SCHEDULED: {WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.IN_PROGRESS: {WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.COMPLETED: set(),
    WorkOrderStatus.CANCELLED: set(),
}


@router.post("/work-orders/{work_order_id}/status", response_model=StatusEventResponse, dependencies=[Depends(require_api_key)])
def update_work_order_status(
    work_order_id: str,
    payload: StatusUpdate,
    db: Session = Depends(get_db),
) -> StatusEventResponse:
    if not payload.confirmed:
        raise HTTPException(status_code=409, detail="Explicit confirmation is required for status changes")
    work_order = db.get(WorkOrder, work_order_id)
    if work_order is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    if payload.status not in _ALLOWED_TRANSITIONS[work_order.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Invalid transition from {work_order.status.value} to {payload.status.value}",
        )

    previous = work_order.status.value
    work_order.status = payload.status
    event = StatusEvent(
        id=f"EVT-{uuid4().hex[:10].upper()}",
        work_order_id=work_order.id,
        from_status=previous,
        to_status=payload.status.value,
        actor="dispatch_api",
        note=payload.note,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return StatusEventResponse.model_validate(event)
