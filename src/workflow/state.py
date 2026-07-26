# File: src/workflow/state.py
from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class AgentState(TypedDict):
    """Shared dictionary state passed between LangGraph workflow nodes."""

<<<<<<< HEAD
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
    matching_score: float | None = None
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
=======
    session_id: str
    user_id: int
    resume_text: str
    job_description: str
    user_resume_json: NotRequired[dict[str, Any]]
    job_target_json: NotRequired[dict[str, Any]]
    drafts: NotRequired[list[dict[str, Any]]]
    feedback: NotRequired[list[str]]
    attempt_count: NotRequired[int]
    target_company: NotRequired[str]
    target_role: NotRequired[str]
    discovered_jobs: NotRequired[list[dict[str, Any]]]
    selected_job: NotRequired[dict[str, Any]]
    extracted_facts: NotRequired[dict[str, Any]]
    optimized_resume: NotRequired[str]
    ats_score: NotRequired[float]
    cover_letter: NotRequired[str]
    email_payload: NotRequired[dict[str, Any]]
    validation_errors: NotRequired[list[str]]
    hitl_gate_1_approved: NotRequired[bool]
    hitl_gate_2_approved: NotRequired[bool]
    hitl_gate_3_approved: NotRequired[bool]
    workflow_status: NotRequired[str]
    metadata: NotRequired[dict[str, Any]]
>>>>>>> bac5900d7d9b4ef2c0b5607ef1cf12e192b4817a
