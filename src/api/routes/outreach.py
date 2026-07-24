# File: src/api/routes/outreach.py
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class OutreachDispatchRequest(BaseModel):
    """Payload for dispatching outbound application outreach."""

    recipient_email: str = Field(..., min_length=3)
    subject: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    attachments: list[str] = Field(default_factory=list)


@router.post("/dispatch")
async def dispatch_outreach(payload: OutreachDispatchRequest) -> dict[str, Any]:
    """Queue an email outreach request."""

    return {"status": "queued", "recipient_email": str(payload.recipient_email)}
