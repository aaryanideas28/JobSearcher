# File: src/workflow/state.py
from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class AgentState(TypedDict):
    """Shared state passed between LangGraph workflow nodes."""

    session_id: str
    user_id: int
    resume_text: str
    job_description: str
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
