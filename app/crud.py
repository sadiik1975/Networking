from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.geo import haversine_miles, resolve_location
from app.models_db import Lead, Trade


def get_lead(db: Session, lead_id: str) -> Lead | None:
    return db.get(Lead, lead_id)


def search_leads(
    db: Session,
    trade: Trade,
    location: str,
    radius_miles: int,
    min_value: float | None,
    ownership_filter: str | None,
    max_results: int,
) -> list[tuple[Lead, float]]:
    """Return (lead, distance_miles) tuples within radius, sorted by distance."""
    origin_lat, origin_lon = resolve_location(location)

    stmt = select(Lead).where(Lead.trade == trade)
    if min_value is not None:
        stmt = stmt.where(Lead.estimated_value >= min_value)
    if ownership_filter:
        stmt = stmt.where(
            func.lower(Lead.ownership_category) == ownership_filter.strip().lower()
        )

    candidates = db.execute(stmt).scalars().all()

    results: list[tuple[Lead, float]] = []
    for lead in candidates:
        distance = haversine_miles(origin_lat, origin_lon, lead.latitude, lead.longitude)
        if distance <= radius_miles:
            results.append((lead, distance))

    results.sort(key=lambda pair: pair[1])
    return results[:max_results]
