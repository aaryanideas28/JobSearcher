# File: src/api/routes/outreach.py
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.workflow.tasks import send_email_outreach_task

router = APIRouter()


class OutreachDispatchRequest(BaseModel):
    """Payload for dispatching outbound application outreach."""

    recipient_email: str = Field(..., min_length=3)
    subject: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    attachments: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/dispatch")
async def dispatch_outreach(payload: OutreachDispatchRequest) -> dict[str, Any]:
    """Queue an email outreach request for asynchronous delivery."""

    dump = getattr(payload, "model_dump", payload.dict)
    message = dump()
    delay = getattr(send_email_outreach_task, "delay", None)
    if callable(delay):
        task = delay(message)
        task_id = getattr(task, "id", None)
    else:
        result = send_email_outreach_task(message)
        task_id = result.get("task_id")
    return {"status": "queued", "recipient_email": payload.recipient_email, "task_id": task_id}
