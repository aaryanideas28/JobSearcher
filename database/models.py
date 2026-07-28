# File: database/models.py
"""SQLAlchemy ORM models for the AI Resume Automation Platform."""

from __future__ import annotations
from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from database.base import Base

def json_column_type() -> JSON:
    """Return a JSON type compatible with SQLite and PostgreSQL."""
    return JSON().with_variant(JSONB, "postgresql")

class User(Base):
    """Application user/candidate account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="Candidate")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    resume_versions: Mapped[list[ResumeVersion]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    job_targets: Mapped[list[JobTarget]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    candidate_preferences: Mapped[list[CandidatePreference]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

class ResumeVersion(Base):
    """Versioned resume text and optimization metadata."""

    __tablename__ = "resume_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version_label: Mapped[str] = mapped_column(String(100), nullable=False, default="original")
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    optimized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ats_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_column_type(), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="resume_versions")


class JobTarget(Base):
    """Job target selected manually or discovered via scraping/search."""

    __tablename__ = "job_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_title: Mapped[str] = mapped_column(String(255), nullable=False)
    job_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="selected")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_column_type(), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="job_targets")


class CandidatePreference(Base):
    """User-provided preferences and skills for optimization/search."""

    __tablename__ = "candidate_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_role: Mapped[str] = mapped_column(String(255), nullable=False)
    experience_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    skills_to_highlight: Mapped[list[str]] = mapped_column(json_column_type(), default=list, nullable=False)
    preferred_locations: Mapped[list[str]] = mapped_column(json_column_type(), default=list, nullable=False)
    work_authorization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_column_type(), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="candidate_preferences")


class WorkflowSession(Base):
    """Workflow run state for HITL review and resumability."""

    __tablename__ = "workflow_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_version_id: Mapped[int | None] = mapped_column(ForeignKey("resume_versions.id", ondelete="SET NULL"), nullable=True)
    job_target_id: Mapped[int | None] = mapped_column(ForeignKey("job_targets.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(100), nullable=False, default="created")
    state_json: Mapped[dict[str, Any]] = mapped_column(json_column_type(), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class HitlDecision(Base):
    """Human approval/rejection decision captured at a workflow gate."""

    __tablename__ = "hitl_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column("workflow_session_id", ForeignKey("workflow_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    gate_name: Mapped[str] = mapped_column(String(50), nullable=False)
    approved: Mapped[bool] = mapped_column(nullable=False, default=False)
    reviewer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    edits_json: Mapped[dict[str, Any]] = mapped_column(json_column_type(), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OutreachEvent(Base):
    """Audit event for generated or sent outreach emails."""

    __tablename__ = "outreach_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_target_id: Mapped[int | None] = mapped_column(ForeignKey("job_targets.id", ondelete="SET NULL"), nullable=True)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(100), nullable=False, default="draft")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_column_type(), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GeneratedDocument(Base):
    """Generated artifacts such as optimized resume PDFs."""

    __tablename__ = "generated_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_version_id: Mapped[int | None] = mapped_column(ForeignKey("resume_versions.id", ondelete="SET NULL"), nullable=True)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_column_type(), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# Legacy models retained for older service imports.
class Candidate(Base):
    """Legacy candidate model."""

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    skills: Mapped[list[str]] = mapped_column(json_column_type(), default=list, nullable=False)
    current_role: Mapped[str | None] = mapped_column(String(255), nullable=True)

    resumes: Mapped[list[Resume]] = relationship(back_populates="candidate", cascade="all, delete-orphan")


class Resume(Base):
    """Legacy resume model."""

    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    candidate: Mapped[Candidate] = relationship(back_populates="resumes")


class Job(Base):
    """Legacy job model."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    requirements: Mapped[list[str]] = mapped_column(json_column_type(), default=list, nullable=False)


__all__ = [
    "Base",
    "User",
    "ResumeVersion",
    "JobTarget",
    "CandidatePreference",
    "WorkflowSession",
    "HitlDecision",
    "OutreachEvent",
    "GeneratedDocument",
    "Candidate",
    "Resume",
    "Job",
]
