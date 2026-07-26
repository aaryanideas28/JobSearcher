from __future__ import annotations

from typing import Annotated, Any, Literal

<<<<<<< HEAD
from fastapi import APIRouter, HTTPException, status
=======
from fastapi import APIRouter, Depends, HTTPException, status
>>>>>>> bac5900d7d9b4ef2c0b5607ef1cf12e192b4817a
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models import HitlDecision, ResumeVersion, WorkflowSession
from src.api.dependencies import get_db

from src.workflow.state import AgentState
from src.workflow.tasks import enqueue_document_render, enqueue_gmail_dispatch

router = APIRouter()


class GateDecision(BaseModel):
    """A reviewer decision plus the current serialized workflow state."""

    session_id: str = Field(..., min_length=1)
    approved: bool
<<<<<<< HEAD
    notes: str | None = Field(default=None, max_length=4000)
    state: dict[str, Any] | None = None


async def _record_gate_decision(
    gate_name: Literal["gate-1", "gate-2", "gate-3"], payload: GateDecision
) -> tuple[AgentState | None, dict[str, Any]]:
    """Apply a gate decision to AgentState and retain reviewer audit metadata."""

    if payload.state is None:
        return None, {"gate": gate_name, "session_id": payload.session_id, "approved": payload.approved, "queued": False}
    try:
        state = AgentState.model_validate(payload.state)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid AgentState payload.") from exc
    if state.session_id and state.session_id != payload.session_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="session_id does not match AgentState.")
    state.session_id = payload.session_id
    setattr(state, f"hitl_{gate_name.replace('-', '_')}_approved", payload.approved)
    state.feedback.append(f"{gate_name}: {'approved' if payload.approved else 'rejected'}" + (f" — {payload.notes}" if payload.notes else ""))
    state.workflow_status = f"{gate_name}_{'approved' if payload.approved else 'rejected'}"
    return state, {"gate": gate_name, "session_id": payload.session_id, "approved": payload.approved, "queued": False}


@router.post("/gate-1")
async def gate_1(payload: GateDecision) -> dict[str, Any]:
    """Approve parsed resume facts before job-target selection continues."""

    state, response = await _record_gate_decision("gate-1", payload)
    if state is not None:
        response["state"] = state.model_dump(mode="json")
    return response


@router.post("/gate-2")
async def gate_2(payload: GateDecision) -> dict[str, Any]:
    """Approve the selected job and queue PDF generation only after approval."""

    state, response = await _record_gate_decision("gate-2", payload)
    if state is None:
        return response
    if payload.approved:
        response["task_id"] = await enqueue_document_render(state)
        response["queued"] = True
    response["state"] = state.model_dump(mode="json")
    return response


@router.post("/gate-3")
async def gate_3(payload: GateDecision) -> dict[str, Any]:
    """Approve the MIME email and queue Gmail dispatch only after approval."""

    state, response = await _record_gate_decision("gate-3", payload)
    if state is None:
        return response
    if payload.approved:
        if not state.email_payload:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="AgentState.email_payload is required for Gmail dispatch.")
        email_payload = {**state.email_payload, "session_id": state.session_id}
        response["task_id"] = await enqueue_gmail_dispatch(email_payload)
        response["queued"] = True
    response["state"] = state.model_dump(mode="json")
    return response
=======
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
>>>>>>> bac5900d7d9b4ef2c0b5607ef1cf12e192b4817a
