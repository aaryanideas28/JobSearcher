# File: src/api/routes/hitl.py
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class GateDecision(BaseModel):
    """Human-in-the-loop approval payload."""

    session_id: str = Field(..., min_length=1)
    approved: bool
    notes: str | None = None


async def _record_gate_decision(gate_name: Literal["gate-1", "gate-2", "gate-3"], payload: GateDecision) -> dict[str, Any]:
    """Placeholder persistence hook for approval gates."""

    return {"gate": gate_name, "session_id": payload.session_id, "approved": payload.approved}


@router.post("/gate-1")
async def gate_1(payload: GateDecision) -> dict[str, Any]:
    """Approve resume parsing and security validation."""

    return await _record_gate_decision("gate-1", payload)


@router.post("/gate-2")
async def gate_2(payload: GateDecision) -> dict[str, Any]:
    """Approve optimized resume draft before compilation."""

    return await _record_gate_decision("gate-2", payload)


@router.post("/gate-3")
async def gate_3(payload: GateDecision) -> dict[str, Any]:
    """Approve outreach dispatch before sending messages."""

    return await _record_gate_decision("gate-3", payload)
