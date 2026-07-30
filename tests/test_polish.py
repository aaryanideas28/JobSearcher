# File: tests/test_polish.py
from __future__ import annotations

import pytest
from src.agents.job_discovery import sanitize_job_card
from src.agents.outreach import OutreachAgent, sanitize_company_name


def test_sanitize_job_card() -> None:
    # 1. Test title cleaning
    card1 = {
        "title": "Page 3 - 37,777 Jobs | Back-End Developer | Shine.com",
        "company": "Fast Company Bangalore",
        "description": "This is a very long description that should be truncated to exactly two lines because it exceeds the standard limit set by the user requirement of a clean snippet card. It has some extra text at the end here.",
        "url": "https://shine.com/jobs/view/123"
    }
    sanitized1 = sanitize_job_card(card1)
    assert sanitized1["title"] == "Back-End Developer"
    assert sanitized1["company"] == "Fast Company"
    assert len(sanitized1["description"]) <= 180
    assert sanitized1["description"].endswith("...")

    # 2. Test fallback company domain extraction
    card2 = {
        "title": "Software Architect",
        "company": "Unknown",
        "url": "https://example.com/jobs/456"
    }
    sanitized2 = sanitize_job_card(card2)
    assert sanitized2["company"] == "Example"


def test_sanitize_company_name() -> None:
    assert sanitize_company_name("Hitech Corp London UK") == "Hitech Corp"
    assert sanitize_company_name("Bangalore, Karnataka Solutions") == "Solutions"
    assert sanitize_company_name("Unknown") == "Hiring Team"


@pytest.mark.anyio
async def test_generate_outreach_email_fallback() -> None:
    agent = OutreachAgent()
    resume_text = "Name: John Doe\nTarget Role: Cloud Architect\nSkills: Go, Kubernetes, GCP"
    job_description = "Looking for a cloud developer to scale Kubernetes systems."
    
    # Run outreach email draft fallback rendering
    body = await agent.draft_cover_letter(
        resume_text=resume_text,
        job_description=job_description,
        company_name="Acme Corp Bangalore"
    )
    
    # Verify fallback structure
    assert "Dear Acme Corp" in body
    assert "John Doe" in body
    assert "Cloud Architect" in body
    assert "Kubernetes" in body
    assert "DOCX format" in body
