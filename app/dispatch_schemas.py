from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

from app.dispatch_models import OutreachChannel, OutreachStatus, WorkOrderStatus
from app.models_db import Trade


class ContractorCreate(BaseModel):
    business_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=30)
    trades: list[Trade] = Field(min_length=1)
    service_zip: str = Field(pattern=r"^\d{5}$")
    service_radius_miles: int = Field(default=50, gt=0, le=500)
    ownership_category: str = "Unverified"
    certification_details: str = "No verified ownership certification provided"
    source_url: HttpUrl | None = None
    license_number: str | None = None
    license_state: str | None = Field(default=None, min_length=2, max_length=2)
    insurance_expiry: date | None = None


class ContractorUpdate(BaseModel):
    business_name: str | None = Field(default=None, min_length=2, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=7, max_length=30)
    service_radius_miles: int | None = Field(default=None, gt=0, le=500)
    ownership_category: str | None = None
    certification_details: str | None = None
    source_url: HttpUrl | None = None
    license_number: str | None = None
    license_state: str | None = Field(default=None, min_length=2, max_length=2)
    insurance_expiry: date | None = None
    active: bool | None = None


class ContractorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_name: str
    email: EmailStr
    phone: str
    trades: list[str]
    service_zip: str
    service_radius_miles: int
    ownership_category: str
    certification_details: str
    source_url: str
    license_number: str | None
    license_state: str | None
    insurance_expiry: date | None
    verified: bool
    active: bool


class ContractorMatch(ContractorResponse):
    distance_miles: float
    match_score: float


class CrewCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    trade: Trade
    capacity: int = Field(default=1, ge=1, le=100)


class CrewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    contractor_id: str
    name: str
    trade: str
    capacity: int
    active: bool


class OutreachCreate(BaseModel):
    lead_id: str
    contractor_id: str
    channel: OutreachChannel
    message: str = Field(min_length=1, max_length=5000)
    confirmed: bool = Field(default=False, description="Must be true to queue an external outreach action")


class OutreachResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lead_id: str
    contractor_id: str
    channel: OutreachChannel
    status: OutreachStatus
    message: str
    created_at: datetime


class ScheduleCreate(BaseModel):
    lead_id: str
    contractor_id: str
    crew_id: str
    scope: str = Field(min_length=1, max_length=10000)
    budget: float | None = Field(default=None, ge=0)
    scheduled_start: datetime
    scheduled_end: datetime
    customer_confirmed: bool = Field(default=False, description="Must be true before a work order is created")
    confirmed: bool = Field(default=False, description="Explicit dispatch confirmation barrier")


class WorkOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lead_id: str
    contractor_id: str
    crew_id: str
    status: WorkOrderStatus
    scope: str
    budget: float | None
    scheduled_start: datetime
    scheduled_end: datetime
    customer_confirmed: bool
    created_at: datetime


class StatusUpdate(BaseModel):
    status: WorkOrderStatus
    note: str | None = Field(default=None, max_length=2000)
    confirmed: bool = Field(default=False, description="Explicit confirmation for lifecycle mutation")


class StatusEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    work_order_id: str
    from_status: str | None
    to_status: str
    actor: str
    note: str | None
    created_at: datetime
