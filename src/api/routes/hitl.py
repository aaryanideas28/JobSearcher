from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.workflow.state import AgentState
from src.workflow.tasks import enqueue_document_render, enqueue_gmail_dispatch

router = APIRouter()


class GateDecision(BaseModel):
    """A reviewer decision plus the current serialized workflow state."""

    session_id: str = Field(..., min_length=1)
    approved: bool
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
