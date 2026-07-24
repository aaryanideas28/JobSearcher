# File: src/api/dependencies.py
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from database.connection import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
