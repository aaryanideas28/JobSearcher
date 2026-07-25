# File: database/models.py
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""


def json_column_type() -> JSON:
    """Return a portable JSON column type for the current database dialect."""

    return JSON().with_variant(JSONB, "postgresql")


class User(Base):
    """Application user who owns resume versions and job targets."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

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
    """Stored version of a resume and its optimization metadata."""

    __tablename__ = "resume_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    version_label: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    optimized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ats_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_column_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="resume_versions")


class JobTarget(Base):
    """Job posting or target role used to tune resume optimization."""

    __tablename__ = "job_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_title: Mapped[str] = mapped_column(String(255), nullable=False)
    job_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    fit_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="discovered", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_column_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="job_targets")


class CandidatePreference(Base):
    """Candidate-provided intake details used to steer optimization."""

    __tablename__ = "candidate_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    target_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    experience_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    skills_to_highlight: Mapped[list[str]] = mapped_column(json_column_type(), default=list)
    preferred_locations: Mapped[list[str]] = mapped_column(json_column_type(), default=list)
    work_authorization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_column_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="candidate_preferences")


class WorkflowSession(Base):
    """Persisted workflow checkpoint for human review and resumable execution."""

    __tablename__ = "workflow_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    resume_version_id: Mapped[int | None] = mapped_column(ForeignKey("resume_versions.id"), nullable=True)
    job_target_id: Mapped[int | None] = mapped_column(ForeignKey("job_targets.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="created", nullable=False)
    state_json: Mapped[dict[str, Any]] = mapped_column(json_column_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class HitlDecision(Base):
    """Recorded human-in-the-loop approval, rejection, or edit."""

    __tablename__ = "hitl_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_session_id: Mapped[str] = mapped_column(ForeignKey("workflow_sessions.id"), nullable=False, index=True)
    gate_name: Mapped[str] = mapped_column(String(50), nullable=False)
    approved: Mapped[bool] = mapped_column(nullable=False)
    reviewer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    edits_json: Mapped[dict[str, Any]] = mapped_column(json_column_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutreachEvent(Base):
    """Email outreach event and provider delivery state."""

    __tablename__ = "outreach_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    job_target_id: Mapped[int | None] = mapped_column(ForeignKey("job_targets.id"), nullable=True)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_column_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GeneratedDocument(Base):
    """Generated resume, cover-letter, report, or diagnostic artifact."""

    __tablename__ = "generated_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    resume_version_id: Mapped[int | None] = mapped_column(ForeignKey("resume_versions.id"), nullable=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(json_column_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
