from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def migrate_schema() -> None:
    """Add new lead metadata columns to an existing SQLite database."""
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "leads" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("leads")}
    additions = {
        "ownership_category": "VARCHAR NOT NULL DEFAULT 'Unverified'",
        "certification_details": "VARCHAR NOT NULL DEFAULT 'No verified ownership certification provided'",
        "source_url": "VARCHAR NOT NULL DEFAULT ''",
    }
    with engine.begin() as connection:
        for column, definition in additions.items():
            if column not in columns:
                connection.execute(text(f"ALTER TABLE leads ADD COLUMN {column} {definition}"))
        if "source_url" in columns or "source_url" in additions:
            connection.execute(
                text("UPDATE leads SET source_url = municipal_source_url WHERE source_url = ''")
            )


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
