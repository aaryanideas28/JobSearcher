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
    candidate_preferences: Mapped[list[CandidatePreference]] = relationship(
        back_populates="user",
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


<<<<<<< HEAD
__all__ = ["Base", "Candidate", "Job", "Resume"]
=======
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
>>>>>>> bac5900d7d9b4ef2c0b5607ef1cf12e192b4817a
