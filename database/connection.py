# File: database/connection.py
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import get_settings
from database.models import Base

settings = get_settings()

connect_args: dict[str, object] = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine: Engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


def init_db() -> None:
    """Initialize database tables for local development."""

    Base.metadata.create_all(bind=engine)


def session_scope() -> Generator[Session, None, None]:
    """Yield a database session and close it after use."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
