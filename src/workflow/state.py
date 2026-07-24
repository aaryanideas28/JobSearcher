# File: src/workflow/state.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

class AgentState(BaseModel):
    """Validated state shared between resume-workflow agents."""

    model_config = ConfigDict(extra="forbid")

    user_resume_json: dict[str, Any] = Field(default_factory=dict)
    job_target_json: dict[str, Any] = Field(default_factory=dict)
    drafts: list[dict[str, Any]] = Field(default_factory=list)
    feedback: list[str] = Field(default_factory=list)
    attempt_count: int = Field(default=0, ge=0)

    session_id: str | None = None
    user_id: int | None = None
    resume_text: str = ""
    job_description: str = ""
    target_company: str | None = None
    target_role: str | None = None
    discovered_jobs: list[dict[str, Any]] = Field(default_factory=list)
    selected_job: dict[str, Any] | None = None
    extracted_facts: dict[str, Any] = Field(default_factory=dict)
    optimized_resume: str = ""
    ats_score: float | None = None
    cover_letter: str = ""
    email_payload: dict[str, Any] = Field(default_factory=dict)
    validation_errors: list[str] = Field(default_factory=list)
    hitl_gate_1_approved: bool | None = None
    hitl_gate_2_approved: bool | None = None
    hitl_gate_3_approved: bool | None = None
    workflow_status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
