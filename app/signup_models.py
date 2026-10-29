from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# The interests the join-the-list form and the visitor agent offer.
SIGNUP_INTERESTS = ("business", "organization", "curious")


class Signup(Base):
    """A join-the-list signup from the public visitor surface.

    Written by POST /signups and by the visitor agent's in-chat capture
    (one list, one storage path — see app.routers.signups.save_signup).
    Owner data: only ever read back through the key-tier GET /signups.
    """

    __tablename__ = "signups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    company: Mapped[str] = mapped_column(String(200), default="")
    interest: Mapped[str] = mapped_column(String(20), default="business")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
