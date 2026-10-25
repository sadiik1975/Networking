from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    company_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    legal_structure: Mapped[str | None] = mapped_column(String(100), nullable=True)
    certifications: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    demographic_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    naics_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    location: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    contact_info: Mapped[dict[str, str | None]] = mapped_column(JSON, nullable=False, default=dict)
    target_global_markets: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
