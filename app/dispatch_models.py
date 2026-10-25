import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OutreachChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    PHONE = "phone"


class OutreachStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    RESPONDED = "responded"
    FAILED = "failed"


class WorkOrderStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    INTERESTED = "interested"
    ASSIGNED = "assigned"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Contractor(Base):
    __tablename__ = "contractors"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    business_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, nullable=False)
    trades: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    service_zip: Mapped[str] = mapped_column(String(5), index=True, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    service_radius_miles: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    ownership_category: Mapped[str] = mapped_column(String, nullable=False, default="Unverified")
    certification_details: Mapped[str] = mapped_column(
        String, nullable=False, default="No verified ownership certification provided"
    )
    source_url: Mapped[str] = mapped_column(String, nullable=False, default="")
    license_number: Mapped[str | None] = mapped_column(String, nullable=True)
    license_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    insurance_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class Crew(Base):
    __tablename__ = "crews"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    contractor_id: Mapped[str] = mapped_column(ForeignKey("contractors.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    trade: Mapped[str] = mapped_column(String, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Outreach(Base):
    __tablename__ = "outreach"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True, nullable=False)
    contractor_id: Mapped[str] = mapped_column(ForeignKey("contractors.id"), index=True, nullable=False)
    channel: Mapped[OutreachChannel] = mapped_column(Enum(OutreachChannel), nullable=False)
    status: Mapped[OutreachStatus] = mapped_column(Enum(OutreachStatus), nullable=False, default=OutreachStatus.QUEUED)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True, nullable=False)
    contractor_id: Mapped[str] = mapped_column(ForeignKey("contractors.id"), index=True, nullable=False)
    crew_id: Mapped[str] = mapped_column(ForeignKey("crews.id"), index=True, nullable=False)
    status: Mapped[WorkOrderStatus] = mapped_column(Enum(WorkOrderStatus), nullable=False, default=WorkOrderStatus.NEW)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    customer_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class StatusEvent(Base):
    __tablename__ = "status_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    work_order_id: Mapped[str] = mapped_column(ForeignKey("work_orders.id"), index=True, nullable=False)
    from_status: Mapped[str | None] = mapped_column(String, nullable=True)
    to_status: Mapped[str] = mapped_column(String, nullable=False)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
