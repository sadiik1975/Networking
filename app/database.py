from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create tables and import any curated events from data/networking_events.json."""
    from app import models, events  # noqa: F401  (registers tables)
    from app import company_models  # noqa: F401
    from app import signup_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        events.import_curated_file_if_empty(db)
    finally:
        db.close()


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
