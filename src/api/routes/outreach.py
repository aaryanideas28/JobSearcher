from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

from src.workflow.tasks import enqueue_gmail_dispatch

router = APIRouter()


class OutreachDispatchRequest(BaseModel):
    """A prebuilt Base64 MIME email ready for asynchronous Gmail dispatch."""

    raw: str | None = None
    base64_mime: str | None = None
    mime_base64: str | None = None
    session_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def requires_mime_payload(self) -> "OutreachDispatchRequest":
        if not any((self.raw, self.base64_mime, self.mime_base64)):
            raise ValueError("Provide a Base64 MIME email in raw, base64_mime, or mime_base64.")
        return self


@router.post("/dispatch")
async def dispatch_outreach(payload: OutreachDispatchRequest) -> dict[str, Any]:
    """Queue Gmail delivery; FastAPI never sends messages in-process."""

    task_id = await enqueue_gmail_dispatch(payload.model_dump(exclude_none=True))
    return {"status": "queued", "task_id": task_id, "session_id": payload.session_id}
