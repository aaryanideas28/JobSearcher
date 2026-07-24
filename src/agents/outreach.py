# File: src/agents/outreach.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EmailPayload:
    """Outbound email payload ready for queue dispatch."""

    recipient_email: str
    subject: str
    body: str
    attachments: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class OutreachAgent:
    """Agent for cover letter generation and email payload assembly."""

    async def draft_cover_letter(self, resume_text: str, job_description: str, company_name: str) -> str:
        """Draft a cover letter for a target company and job."""

        _ = (resume_text, job_description)
        return f"Dear {company_name} Hiring Team,\n\nPlease consider my application.\n"

    def build_email_payload(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        attachments: list[str] | None = None,
    ) -> EmailPayload:
        """Build a normalized email payload for delivery workers."""

        return EmailPayload(
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            attachments=attachments or [],
        )
