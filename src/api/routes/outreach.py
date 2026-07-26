from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

from src.workflow.tasks import enqueue_gmail_dispatch

from src.workflow.tasks import send_email_outreach_task

router = APIRouter()


class OutreachDispatchRequest(BaseModel):
    """A prebuilt Base64 MIME email ready for asynchronous Gmail dispatch."""

<<<<<<< HEAD
    raw: str | None = None
    base64_mime: str | None = None
    mime_base64: str | None = None
    session_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def requires_mime_payload(self) -> "OutreachDispatchRequest":
        if not any((self.raw, self.base64_mime, self.mime_base64)):
            raise ValueError("Provide a Base64 MIME email in raw, base64_mime, or mime_base64.")
        return self
=======
    recipient_email: str = Field(..., min_length=3)
    subject: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    attachments: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
>>>>>>> bac5900d7d9b4ef2c0b5607ef1cf12e192b4817a


@router.post("/dispatch")
async def dispatch_outreach(payload: OutreachDispatchRequest) -> dict[str, Any]:
<<<<<<< HEAD
    """Queue Gmail delivery; FastAPI never sends messages in-process."""

    task_id = await enqueue_gmail_dispatch(payload.model_dump(exclude_none=True))
    return {"status": "queued", "task_id": task_id, "session_id": payload.session_id}
=======
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
>>>>>>> bac5900d7d9b4ef2c0b5607ef1cf12e192b4817a
