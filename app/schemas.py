from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, model_validator

from app.models_db import LeadStatus, ProjectScale, Trade


class LeadSummary(BaseModel):
    """Sanitized lead object returned by the search endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    trade: Trade
    project_type: str
    description: str
    city: str
    state: str
    zip_code: str
    distance_miles: float = Field(..., ge=0, description="Distance from the queried location, in miles")
    estimated_value: float | None = None
    issue_date: date
    project_scale: ProjectScale
    municipal_source_url: HttpUrl
    ownership_category: str
    certification_details: str
    source_url: str


class LeadDetail(BaseModel):
    """Deep-dive lead specification for dispatch."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    trade: Trade
    project_type: str
    description: str

    address_line1: str
    city: str
    state: str
    zip_code: str
    latitude: float
    longitude: float

    issue_date: date
    estimated_value: float | None = None
    project_scale: ProjectScale
    permit_number: str
    status: LeadStatus
    verified: bool

    ownership_category: str
    certification_details: str
    source_url: str

    municipal_source_url: HttpUrl
    municipal_contact_name: str
    municipal_contact_phone: str
    municipal_contact_email: EmailStr


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str


class ErrorResponse(BaseModel):
    detail: str


class CompanyLocation(BaseModel):
    city: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=1, max_length=120)
    country: str = Field(min_length=1, max_length=120)


class CompanyContactInfo(BaseModel):
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    website: HttpUrl | None = None


class CompanyProfileCreate(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    legal_structure: str | None = Field(default=None, max_length=100)
    certifications: list[str] = Field(default_factory=list, max_length=50)
    demographic_tags: list[str] = Field(default_factory=list, max_length=50)
    naics_code: str | None = Field(default=None, pattern=r"^\d{2,6}$")
    location: CompanyLocation
    contact_info: CompanyContactInfo = Field(default_factory=CompanyContactInfo)
    target_global_markets: list[str] = Field(default_factory=list, max_length=100)
    description: str = Field(min_length=1, max_length=5000)
    capabilities: list[str] = Field(default_factory=list, max_length=100)


class CompanyProfileUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=2, max_length=200)
    legal_structure: str | None = Field(default=None, max_length=100)
    certifications: list[str] | None = Field(default=None, max_length=50)
    demographic_tags: list[str] | None = Field(default=None, max_length=50)
    naics_code: str | None = Field(default=None, pattern=r"^\d{2,6}$")
    location: CompanyLocation | None = None
    contact_info: CompanyContactInfo | None = None
    target_global_markets: list[str] | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    capabilities: list[str] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        required_fields = {
            "company_name",
            "certifications",
            "demographic_tags",
            "location",
            "contact_info",
            "target_global_markets",
            "description",
            "capabilities",
        }
        if any(
            field in self.model_fields_set and getattr(self, field) is None
            for field in required_fields
        ):
            raise ValueError("Required profile fields cannot be null")
        return self


class CompanyProfileResponse(CompanyProfileCreate):
    model_config = ConfigDict(from_attributes=True)

    company_id: str


class CompanyMatchResponse(BaseModel):
    company: str
    company_id: str
    score: float = Field(ge=0, le=1)
    tags: list[str]


class MatchResponse(BaseModel):
    query: str
    matches: list[CompanyMatchResponse]
