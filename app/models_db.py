import enum
from datetime import date

from sqlalchemy import Boolean, Date, Enum, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Trade(str, enum.Enum):
    ELECTRICAL = "electrical"
    ROOFING = "roofing"
    PLUMBING = "plumbing"
    HVAC = "hvac"
    GENERAL_CONTRACTING = "general_contracting"
    FLOORING = "flooring"
    LANDSCAPING = "landscaping"
    FENCING = "fencing"
    SOLAR = "solar"
    REMODELING = "remodeling"


class ProjectScale(str, enum.Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class LeadStatus(str, enum.Enum):
    OPEN = "open"
    DISPATCHED = "dispatched"
    CLOSED = "closed"


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    trade: Mapped[Trade] = mapped_column(Enum(Trade), index=True, nullable=False)
    project_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)

    address_line1: Mapped[str] = mapped_column(String, nullable=False)
    city: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(5), index=True, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    estimated_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    project_scale: Mapped[ProjectScale] = mapped_column(Enum(ProjectScale), nullable=False)
    permit_number: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[LeadStatus] = mapped_column(Enum(LeadStatus), default=LeadStatus.OPEN, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    ownership_category: Mapped[str] = mapped_column(String, default="Unverified", nullable=False)
    certification_details: Mapped[str] = mapped_column(
        String, default="No verified ownership certification provided", nullable=False
    )
    source_url: Mapped[str] = mapped_column(String, default="", nullable=False)

    municipal_source_url: Mapped[str] = mapped_column(String, nullable=False)
    municipal_contact_name: Mapped[str] = mapped_column(String, nullable=False)
    municipal_contact_phone: Mapped[str] = mapped_column(String, nullable=False)
    municipal_contact_email: Mapped[str] = mapped_column(String, nullable=False)
