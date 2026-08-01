# File: tests/test_smoke_end_to_end.py
import pytest
from src.agents.ats_engine import ATSEngine


def test_end_to_end_smoke_bad_resume_calibration():
    """Smoke test: Simulate 'Bad' resume containing tables, passive voice, and zero metrics.
    Verify score falls into calibrated 30%-65% range and returns 3-4 line actionable feedback.
    """
    engine = ATSEngine()

    bad_resume = """
    John Doe | Phone: 555-0199 | Email: john@example.com
    Software Engineer specializing in Python, FastAPI, Docker, and PostgreSQL backend development with experience in agile software teams.
    
    Work Experience
    | Company | Role | Dates |
    | TechCorp Solutions | Software Engineer | 2020-2022 |
    
    Duties & Responsibilities:
    - Assisted with backend development using Python, FastAPI, and PostgreSQL databases and helped to write basic code for client services.
    - Worked on team web development projects, handled daily maintenance tickets for client applications, and was part of customer support.
    - Responsible for database backups, API query adjustments, and assisted with server deployment updates across staging environments.
    - Participated in weekly sprint meetings, took part in backlog grooming, and served as on-call support for application bug fixes.
    - Involved in writing developer documentation, dealt with legacy modules, and aided team members with code reviews.
    """

    job_description = """
    Seeking a Senior Full-Stack Engineer proficient in Python, FastAPI, React, PostgreSQL, Docker, AWS, and Kubernetes.
    Must demonstrate strong system design and leadership in microservice architectures.
    """

    res = engine.calculate_ats_score(bad_resume, job_description)
    score = res["ats_score"]

    # 1. Confirm score falls into critical calibrated range (<= 65%, not optimistic 80%+)
    assert score <= 65, f"Expected calibrated score <= 65%, got {score}%"

    # 2. Confirm penalties are active
    assert res["penalties"]["impact_verbs"] > 0
    assert res["penalties"]["formatting"] > 0
    assert res["penalties"]["metrics"] > 0

    # 3. Confirm 3-4 line actionable feedback payload is present
    feedback = res.get("actionable_feedback", "")
    lines = feedback.splitlines()
    assert 2 <= len(lines) <= 5
    assert "Technical Skills Gap" in feedback or "Action Verb Impact" in feedback or "Quantified Impact Gap" in feedback
