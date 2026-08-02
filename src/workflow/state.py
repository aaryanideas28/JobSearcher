# File: src/workflow/state.py
"""Shared LangGraph state contract for the AI resume workflow."""

from __future__ import annotations

from typing import Any, TypedDict
try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired



class AgentState(TypedDict):
    """State keys carried through the resume automation workflow."""

    session_id: str
    user_id: int
    job_id: NotRequired[int]
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
    preferred_locations: NotRequired[list[str]]
    work_mode: NotRequired[str]
    discovered_jobs: NotRequired[list[dict[str, Any]]]
    selected_job: NotRequired[dict[str, Any]]
    extracted_facts: NotRequired[dict[str, Any]]
    optimized_resume: NotRequired[str | dict[str, Any]]
    ats_score: NotRequired[float]
    matching_score: NotRequired[float]
    ats_details: NotRequired[dict[str, Any]]
    cover_letter: NotRequired[str]
    email_payload: NotRequired[dict[str, Any]]
    validation_errors: NotRequired[list[str]]
    quality_checks: NotRequired[dict[str, Any]]
    hitl_gate_1_approved: NotRequired[bool]
    hitl_gate_2_approved: NotRequired[bool]
    hitl_gate_3_approved: NotRequired[bool]
    optimization_recommended: NotRequired[bool]
    approve_optimization: NotRequired[bool]
    intake_mode: NotRequired[str]
    structured_intake: NotRequired[dict[str, Any]]
    workflow_status: NotRequired[str]
    needs_optimization_approval: NotRequired[bool]
    metadata: NotRequired[dict[str, Any]]
    original_uploaded_file: NotRequired[str]
    active_resume: NotRequired[str]
    recommendation: NotRequired[str]
    information_density: NotRequired[dict[str, Any]]
    uploaded_resume_text: NotRequired[str]
    keep_original: NotRequired[bool]
    action: NotRequired[str]
    candidate_context: NotRequired[dict[str, Any] | str]
    candidate_name: NotRequired[str]
    email: NotRequired[str]
    phone: NotRequired[str]
    core_skills: NotRequired[list[str]]
