# File: src/api/routes/hitl.py
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models import HitlDecision, ResumeVersion, WorkflowSession
from src.api.dependencies import get_db

router = APIRouter()


class GateDecision(BaseModel):
    """Human-in-the-loop approval payload."""

    session_id: str = Field(..., min_length=1)
    approved: bool
    reviewer_email: str | None = None
    notes: str | None = None
    edited_resume: str | None = None
    edited_email_body: str | None = None
    edited_email_subject: str | None = None


async def _record_gate_decision(
    gate_name: Literal["gate-1", "gate-2", "gate-3"],
    payload: GateDecision,
    db: Session,
) -> dict[str, Any]:
    """Normalize a human approval into the workflow state transition contract."""

    if not payload.approved and not payload.notes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rejections require reviewer notes.",
        )
    next_status = "approved" if payload.approved else "needs_revision"
    edits = {
        "edited_resume": payload.edited_resume,
        "edited_email_body": payload.edited_email_body,
        "edited_email_subject": payload.edited_email_subject,
    }
    edits = {key: value for key, value in edits.items() if value}

    session = db.get(WorkflowSession, payload.session_id)
    if session is not None:
        state = dict(session.state_json or {})
        if payload.edited_resume:
            state["optimized_resume"] = payload.edited_resume
            if session.resume_version_id is not None:
                resume_version = db.get(ResumeVersion, session.resume_version_id)
                if resume_version is not None:
                    resume_version.optimized_text = payload.edited_resume
                    db.add(resume_version)

        email_draft = dict(state.get("email_draft") or {})
        if payload.edited_email_body:
            email_draft["body"] = payload.edited_email_body
        if payload.edited_email_subject:
            email_draft["subject"] = payload.edited_email_subject
        if email_draft:
            state["email_draft"] = email_draft

        session.state_json = state
        session.status = f"{gate_name}:{next_status}"
        db.add(session)
        db.add(
            HitlDecision(
                workflow_session_id=payload.session_id,
                gate_name=gate_name,
                approved=payload.approved,
                reviewer_email=payload.reviewer_email,
                notes=payload.notes,
                edits_json=edits,
            )
        )
        db.commit()

    return {
        "gate": gate_name,
        "session_id": payload.session_id,
        "approved": payload.approved,
        "reviewer_email": payload.reviewer_email,
        "workflow_status": f"{gate_name}:{next_status}",
        "notes": payload.notes,
        "edits_applied": edits,
        "persisted": session is not None,
    }


@router.post("/gate-1")
async def gate_1(payload: GateDecision, db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    """Approve resume parsing and security validation."""

    return await _record_gate_decision("gate-1", payload, db)


@router.post("/gate-2")
async def gate_2(payload: GateDecision, db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    """Approve optimized resume draft before compilation."""

    return await _record_gate_decision("gate-2", payload, db)


@router.post("/gate-3")
async def gate_3(payload: GateDecision, db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    """Approve outreach dispatch before sending messages."""

    return await _record_gate_decision("gate-3", payload, db)
