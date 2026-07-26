"""Core SQLAlchemy models for candidates, resumes, and job postings."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from database.base import Base


def json_column_type() -> JSON:
    """Return a JSON type compatible with SQLite and PostgreSQL."""

    return JSON().with_variant(JSONB, "postgresql")


class Job(Base):
    """A job posting evaluated by the matching and ATS engines."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    requirements: Mapped[list[str]] = mapped_column(json_column_type(), default=list, nullable=False)


class Candidate(Base):
    """A candidate whose resumes are processed by the application."""

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    skills: Mapped[list[str]] = mapped_column(json_column_type(), default=list, nullable=False)
    current_role: Mapped[str | None] = mapped_column(String(255), nullable=True)

    resumes: Mapped[list[Resume]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )


class Resume(Base):
    """A candidate resume with original content and extracted plain text."""

    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    candidate: Mapped[Candidate] = relationship(back_populates="resumes")


__all__ = ["Base", "Candidate", "Job", "Resume"]
