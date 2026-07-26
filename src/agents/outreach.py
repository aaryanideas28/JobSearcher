# File: src/agents/outreach.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.agents.router import TaskComplexityRouter
from src.clients.ollama import OllamaClient

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

    def __init__(self, router: TaskComplexityRouter | None = None, llm_client: OllamaClient | None = None) -> None:
        self.router = router or TaskComplexityRouter(complexity_threshold=0.35)
        self.llm_client = llm_client or OllamaClient()

    async def draft_cover_letter(self, resume_text: str, job_description: str, company_name: str) -> str:
        """Draft a cover letter for a target company and job."""

        prompt = (
            "Draft a concise, truthful outreach email body for a job application.\n\n"
            "Rules:\n"
            "- Do not invent facts.\n"
            "- Keep it under 180 words.\n"
            "- Mention company fit and relevant skills from the resume.\n\n"
            f"Company: {company_name}\n\n"
            f"Resume:\n{resume_text}\n\n"
            f"Job description:\n{job_description}\n"
        )
        decision = self.router.select_model(prompt, {"job_description": job_description})
        generation = await self.llm_client.generate(
            model=decision.model_name,
            system="You write concise, professional job application outreach emails.",
            prompt=prompt,
        )
        if generation.used_fallback or not generation.text:
            return (
                f"Dear {company_name} Hiring Team,\n\n"
                "I am excited to apply for this role. My background aligns with the requirements in the job description, "
                "and I would welcome the opportunity to contribute to your team.\n\n"
                "Thank you for your time and consideration.\n"
            )
        return generation.text

    def build_email_payload(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        attachments: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EmailPayload:
        """Build a normalized email payload for delivery workers."""

        return EmailPayload(
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            attachments=attachments or [],
            metadata=metadata or {},
        )
