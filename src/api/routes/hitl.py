# File: src/api/routes/hitl.py
"""Human-in-the-loop approval gates."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models import HitlDecision, ResumeVersion, WorkflowSession
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


def _record_gate_decision(gate_name: str, payload: GateDecision, db: Session) -> dict[str, Any]:
    """Persist gate decision and apply reviewer edits when possible."""
    if not payload.approved and not payload.notes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rejection requires notes so the agent can revise.",
        )

    edits_applied: list[str] = []
    session: WorkflowSession | None = None

    if payload.session_id:
        session = db.get(WorkflowSession, payload.session_id)

    if session is not None:
        state = dict(session.state_json or {})

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
        session.status = f"{gate_name}_{'approved' if payload.approved else 'rejected'}"

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

    return {
        "status": "approved" if payload.approved else "rejected",
        "gate": gate_name,
        "session_id": payload.session_id,
        "persisted": session is not None,
        "edits_applied": edits_applied,
        "next_action": "continue_workflow" if payload.approved else "revise_draft",
    }


@router.post("/gate-1")
def approve_gate_1(payload: GateDecision, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Approve or reject resume selection."""
    return _record_gate_decision("gate-1", payload, db)


@router.post("/gate-2")
def approve_gate_2(payload: GateDecision, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Approve or reject selected job target."""
    return _record_gate_decision("gate-2", payload, db)


@router.post("/gate-3")
def approve_gate_3(payload: GateDecision, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Approve or reject final optimized resume and email draft."""
    return _record_gate_decision("gate-3", payload, db)
