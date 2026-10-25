from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

EVENT_STATUSES = ("discovered", "interested", "registered", "attended", "skipped")
FOLLOWUP_STATUSES = ("new", "drafted", "sent", "replied", "closed")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    time: Mapped[str] = mapped_column(String(60), default="")
    state: Mapped[str] = mapped_column(String(2), index=True)
    location: Mapped[str] = mapped_column(String(300), default="")
    format: Mapped[str] = mapped_column(String(20))
    organizer: Mapped[str] = mapped_column(String(300))
    target_groups: Mapped[list[str]] = mapped_column(JSON, default=list)
    registration_url: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="interested", index=True)
    brand: Mapped[str | None] = mapped_column(String(30), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    event_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    event_context: Mapped[str] = mapped_column(String(300), default="")
    capture_type: Mapped[str] = mapped_column(String(40), default="manual")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    brand: Mapped[str | None] = mapped_column(String(30), nullable=True)
    followup_status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
