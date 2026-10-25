from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, model_validator


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    event_date: date
    state: str = Field(min_length=2, max_length=2)
    event_format: str
    organizer: str = Field(min_length=1, max_length=300)
    registration_url: HttpUrl
    target_groups: list[str] = Field(default_factory=list, max_length=20)
    location: str = Field(default="", max_length=300)
    time: str = Field(default="", max_length=60)
    status: str = "interested"
    brand: str | None = None
    notes: str = Field(default="", max_length=5000)


class EventUpdate(BaseModel):
    status: str | None = None
    brand: str | None = None
    notes: str | None = Field(default=None, max_length=5000)


class ContactCreate(BaseModel):
    capture_type: str = "manual"
    raw_text: str = Field(default="", max_length=10000)
    event_context: str = Field(default="", max_length=300)
    event_id: str | None = None
    name: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=60)
    notes: str = Field(default="", max_length=5000)
    brand: str | None = None


class ContactUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=60)
    notes: str | None = Field(default=None, max_length=5000)
    brand: str | None = None
    followup_status: str | None = None


class FollowupRequest(BaseModel):
    brand: str
    offering_focus: str
    highlights: list[str] = Field(default_factory=list, max_length=10)


class CompatibilityRequest(BaseModel):
    brand: str
    prospect_name: str = Field(min_length=1, max_length=200)
    industry: str = Field(default="", max_length=200)
    prospect_type: str = "potential_client"
    certified_wmbe_or_mbe: bool = False
    community_affiliated: bool = False
    perceived_needs: list[str] = Field(default_factory=list, max_length=20)


class ReminderRequest(BaseModel):
    days_ahead: int = Field(default=7, ge=1, le=60)
    confirmed: bool = False


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
