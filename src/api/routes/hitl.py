# File: src/api/routes/hitl.py
"""Human-in-the-loop approval gates."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database.models import HitlDecision, ResumeVersion, WorkflowSession, JobTarget
from src.api.dependencies import get_db

router = APIRouter()


class GateDecision(BaseModel):
    """Request payload for HITL approval gates."""

    session_id: str | None = None
    approved: bool = Field(default=False)
    reviewer_email: str | None = None
    notes: str | None = None
    edited_resume: str | None = None
    edited_email_subject: str | None = None
    edited_email_body: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


async def _record_gate_decision(gate_name: str, payload: GateDecision, db: Session) -> dict[str, Any]:
    """Persist gate decision, apply edits, and resume the workflow graph."""
    if not payload.approved and not payload.notes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rejection requires notes so the agent can revise.",
        )

    session: WorkflowSession | None = None
    if payload.session_id:
        session = db.get(WorkflowSession, payload.session_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow session not found.",
        )

    state = dict(session.state_json or {})
    edits_applied: list[str] = []

    if payload.edited_resume:
        state["optimized_resume"] = payload.edited_resume
        if session.resume_version_id is not None:
            resume_version = db.get(ResumeVersion, session.resume_version_id)
            if resume_version is not None:
                resume_version.optimized_text = payload.edited_resume
        edits_applied.append("optimized_resume")

    if payload.edited_email_subject or payload.edited_email_body:
        email_draft = dict(state.get("email_draft") or state.get("email_payload") or {})
        if payload.edited_email_subject:
            email_draft["subject"] = payload.edited_email_subject
            edits_applied.append("email_subject")
        if payload.edited_email_body:
            email_draft["body"] = payload.edited_email_body
            edits_applied.append("email_body")
        state["email_draft"] = email_draft
        state["email_payload"] = email_draft

    state[f"{gate_name}_approved"] = payload.approved
    state[f"{gate_name}_notes"] = payload.notes
    session.state_json = state

    db.add(
        HitlDecision(
            session_id=session.id,
            gate_name=gate_name,
            approved=payload.approved,
            reviewer_email=payload.reviewer_email,
            notes=payload.notes,
            edits_json={
                "edited_resume": payload.edited_resume,
                "edited_email_subject": payload.edited_email_subject,
                "edited_email_body": payload.edited_email_body,
                "metadata": payload.metadata,
            },
        )
    )
    db.commit()

    if payload.approved:
        from src.workflow.graph import graph
        config = {"configurable": {"thread_id": session.id}}

        values: dict[str, Any] = {
            f"hitl_{gate_name.replace('-', '_')}_approved": True,
        }
        if payload.edited_resume:
            values["resume_text"] = payload.edited_resume
            values["optimized_resume"] = payload.edited_resume
        if payload.edited_email_body or payload.edited_email_subject:
            values["email_payload"] = state.get("email_payload") or {}

        if gate_name == "gate-2":
            selected_job = None
            if payload.metadata and "selected_job" in payload.metadata:
                selected_job = payload.metadata["selected_job"]
            elif payload.metadata and "job_target_id" in payload.metadata:
                job_target = db.get(JobTarget, payload.metadata["job_target_id"])
                if job_target:
                    selected_job = {
                        "title": job_target.role_title,
                        "company": job_target.company_name,
                        "url": job_target.job_url,
                        "description": job_target.job_description,
                    }
            if selected_job:
                values["selected_job"] = selected_job

        node_map = {
            "gate-1": "resume_optimizer",
            "gate-2": "outreach",
            "gate-3": "dispatch_outreach",
        }
        target_node = node_map.get(gate_name, gate_name)

        # Update the graph state
        await graph.aupdate_state(config, values, as_node=target_node)

        # Resume the graph
        resumed_state = await graph.ainvoke(None, config=config)

        if isinstance(resumed_state, dict):
            session.state_json = dict(resumed_state)
            session.status = resumed_state.get("workflow_status") or "running"
            db.commit()
    else:
        session.status = f"{gate_name}_rejected"
        db.commit()

    return {
        "status": "approved" if payload.approved else "rejected",
        "gate": gate_name,
        "session_id": payload.session_id,
        "persisted": True,
        "edits_applied": edits_applied,
        "next_action": "continue_workflow" if payload.approved else "revise_draft",
    }


@router.post("/gate-1")
async def approve_gate_1(payload: GateDecision, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Approve or reject resume selection."""
    return await _record_gate_decision("gate-1", payload, db)


@router.post("/gate-2")
async def approve_gate_2(payload: GateDecision, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Approve or reject selected job target."""
    return await _record_gate_decision("gate-2", payload, db)


@router.post("/gate-3")
async def approve_gate_3(payload: GateDecision, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Approve or reject final optimized resume and email draft."""
    return await _record_gate_decision("gate-3", payload, db)
