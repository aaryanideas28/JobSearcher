# File: src/api/routes/outreach.py
"""Outreach API routes."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.workflow.tasks import send_email_outreach_task

router = APIRouter()


class OutreachDispatchRequest(BaseModel):
    """Request payload for dispatching outreach email."""

    recipient_email: str = Field(..., min_length=3)
    subject: str
    body: str
    attachments: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/dispatch")
def dispatch_outreach(payload: OutreachDispatchRequest) -> dict[str, Any]:
    """Queue or execute an outreach email dispatch."""
    from src.config.settings import get_settings
    settings = get_settings()
    email_payload = payload.model_dump()

    if settings.celery_task_always_eager:
        result = send_email_outreach_task(email_payload)
        return {
            "status": result.get("status", "executed"),
            "recipient_email": payload.recipient_email,
            "task_id": str(uuid4()),
            "result": result,
        }

    delay = getattr(send_email_outreach_task, "delay", None)
    if callable(delay):
        async_result = delay(email_payload)
        task_id = getattr(async_result, "id", str(uuid4()))
        return {"status": "queued", "recipient_email": payload.recipient_email, "task_id": task_id}

    result = send_email_outreach_task(email_payload)
    return {
        "status": result.get("status", "executed"),
        "recipient_email": payload.recipient_email,
        "task_id": str(uuid4()),
        "result": result,
    }
