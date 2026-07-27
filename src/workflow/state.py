# File: src/workflow/state.py
"""Shared LangGraph state contract for the AI resume workflow."""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class AgentState(TypedDict):
    """State keys carried through the resume automation workflow."""

    session_id: str
    user_id: int
    resume_text: str
    job_description: str
    user_resume_json: NotRequired[dict[str, Any]]
    job_target_json: NotRequired[dict[str, Any]]
    candidate_preference_json: NotRequired[dict[str, Any]]
    drafts: NotRequired[list[dict[str, Any]]]
    feedback: NotRequired[list[str]]
    attempt_count: NotRequired[int]
    target_company: NotRequired[str]
    target_role: NotRequired[str]
    skills_to_highlight: NotRequired[list[str]]
    discovered_jobs: NotRequired[list[dict[str, Any]]]
    selected_job: NotRequired[dict[str, Any]]
    extracted_facts: NotRequired[dict[str, Any]]
    optimized_resume: NotRequired[str]
    ats_score: NotRequired[float]
    ats_details: NotRequired[dict[str, Any]]
    cover_letter: NotRequired[str]
    email_payload: NotRequired[dict[str, Any]]
    validation_errors: NotRequired[list[str]]
    quality_checks: NotRequired[dict[str, Any]]
    hitl_gate_1_approved: NotRequired[bool]
    hitl_gate_2_approved: NotRequired[bool]
    hitl_gate_3_approved: NotRequired[bool]
    workflow_status: NotRequired[str]
    metadata: NotRequired[dict[str, Any]]
