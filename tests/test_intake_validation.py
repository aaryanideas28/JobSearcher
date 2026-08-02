# File: tests/test_intake_validation.py
import pytest
from fastapi import HTTPException

from src.security.validation import validate_candidate_intake, IntakeRequest
from src.workflow.graph import process_intake
from src.agents.optimizer import ResumeOptimizer


def test_validate_candidate_intake_case1_unselected_mode():
    """CASE 1: Raise HTTP 400 when intake_mode is None or unselected."""
    with pytest.raises(HTTPException) as exc_info:
        validate_candidate_intake({"intake_mode": None})
    assert exc_info.value.status_code == 400
    assert "Please select an intake option" in exc_info.value.detail


def test_validate_candidate_intake_case2_upload_missing_file():
    """CASE 2: Raise HTTP 400 when intake_mode is 'upload' but file/parsed text is missing."""
    with pytest.raises(HTTPException) as exc_info:
        validate_candidate_intake({"intake_mode": "upload", "file_attached": False})
    assert exc_info.value.status_code == 400
    assert "No resume file detected" in exc_info.value.detail


def test_validate_candidate_intake_case3_scratch_missing_fields():
    """CASE 3: Raise HTTP 400 when intake_mode is 'build_from_scratch' but required fields are empty."""
    with pytest.raises(HTTPException) as exc_info:
        validate_candidate_intake({
            "intake_mode": "build_from_scratch",
            "full_name": "",
            "email": "",
            "technical_skills": [],
            "work_experience": [],
        })
    assert exc_info.value.status_code == 400
    assert "Incomplete resume form" in exc_info.value.detail


def test_validate_candidate_intake_valid_upload():
    """Valid upload intake payload passes validation cleanly."""
    validate_candidate_intake({
        "intake_mode": "upload",
        "file_attached": True,
        "parsed_text": "Experienced Python engineer resume content...",
    })


def test_validate_candidate_intake_valid_scratch():
    """Valid build from scratch intake payload passes validation cleanly."""
    validate_candidate_intake({
        "intake_mode": "build_from_scratch",
        "full_name": "Jane Developer",
        "email": "jane@example.com",
        "technical_skills": ["Python", "FastAPI", "SQL"],
        "work_experience": ["Senior Backend Developer at CloudCorp"],
    })


def test_process_intake_entry_node_missing_data_guardrail():
    """At workflow entry node process_intake, set error to MISSING_INTAKE_DATA if empty."""
    empty_state = {"intake_mode": "upload", "resume_text": "", "structured_intake": {}}
    res = process_intake(empty_state)
    assert res.get("error") == "MISSING_INTAKE_DATA"
    assert res.get("workflow_status") == "failed"


@pytest.mark.asyncio
async def test_optimizer_handles_empty_context_without_raising():
    """The optimizer safely returns empty raw resume text without candidate context."""
    optimizer = ResumeOptimizer()
    with pytest.raises(ValueError) as exc_info:
        await optimizer.optimize_resume(resume_text="", job_description="Software Engineer job")
    assert "Cannot invoke optimizer on empty candidate context" in str(exc_info.value)

    assert await optimizer.build_resume_from_skills(skills=[], target_role="") == ""
