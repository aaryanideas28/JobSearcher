# File: tests/test_hitl_optimization.py
from __future__ import annotations

import pytest
from src.workflow.graph import check_ats_threshold, check_ats_threshold_routing
from src.workflow.state import AgentState


def test_check_ats_threshold_below_80() -> None:
    state: AgentState = {
        "session_id": "session-test-low",
        "user_id": 1,
        "resume_text": "Sample baseline resume",
        "job_description": "Sample JD",
        "ats_score": 0.65,  # 65% (below 80%)
    }

    updated = check_ats_threshold(state)
    assert updated["optimization_recommended"] is True
    assert updated["workflow_status"] == "PAUSED_FOR_HUMAN_OPTIMIZATION_APPROVAL"


def test_check_ats_threshold_above_80() -> None:
    state: AgentState = {
        "session_id": "session-test-high",
        "user_id": 1,
        "resume_text": "Sample high ATS resume",
        "job_description": "Sample JD",
        "ats_score": 0.85,  # 85% (above 80%)
    }

    updated = check_ats_threshold(state)
    assert updated["optimization_recommended"] is False
    assert updated.get("workflow_status") != "PAUSED_FOR_HUMAN_OPTIMIZATION_APPROVAL"


def test_check_ats_threshold_routing_low() -> None:
    state: AgentState = {
        "session_id": "session-test-low",
        "user_id": 1,
        "resume_text": "Sample baseline resume",
        "job_description": "Sample JD",
        "ats_score": 0.72,  # 72%
    }
    route = check_ats_threshold_routing(state)
    assert route == "paused"


def test_check_ats_threshold_routing_high() -> None:
    state: AgentState = {
        "session_id": "session-test-high",
        "user_id": 1,
        "resume_text": "Sample high ATS resume",
        "job_description": "Sample JD",
        "ats_score": 0.88,  # 88%
    }
    route = check_ats_threshold_routing(state)
    assert route == "proceed"


def test_endpoint_optimization_decision_not_found() -> None:
    from fastapi.testclient import TestClient
    from src.api.main import app
    client = TestClient(app)
    
    response = client.post(
        "/api/v1/hitl/resume-optimization-decision",
        json={"user_id": 9999, "job_id": "9999", "action": "proceed_as_is"}
    )
    assert response.status_code == 404
    assert "session not found" in response.json()["detail"].lower()


def test_check_ats_threshold_scratch_bypass() -> None:
    state: AgentState = {
        "session_id": "session-test-scratch",
        "user_id": 1,
        "resume_text": "Sample scratch resume",
        "job_description": "Sample JD",
        "ats_score": 0.45,  # below 80%
        "intake_mode": "build_from_scratch",
    }

    updated = check_ats_threshold(state)
    assert updated["optimization_recommended"] is False
    assert updated["workflow_status"] == "ats_scored"


def test_check_ats_threshold_routing_scratch_bypass() -> None:
    state: AgentState = {
        "session_id": "session-test-scratch",
        "user_id": 1,
        "resume_text": "Sample scratch resume",
        "job_description": "Sample JD",
        "ats_score": 0.50,  # below 80%
        "intake_mode": "build_from_scratch",
    }
    route = check_ats_threshold_routing(state)
    assert route == "proceed"


def test_structured_intake_endpoint() -> None:
    from fastapi.testclient import TestClient
    from src.api.main import app
    client = TestClient(app)

    payload = {
        "full_name": "Scratch User",
        "contact_info": {
            "email": "scratch@example.com",
            "phone": "555-555-5555",
            "location": "Remote",
            "target_role": "Backend Engineer",
            "preferred_locations": ["Mumbai"],
            "work_mode": "Remote Only"
        },
        "professional_summary": "Experienced python developer.",
        "education": [
            {
                "institution": "MIT",
                "degree": "MS",
                "specialization": "CS",
                "graduation_year": "2023",
                "cgpa_percentage": "3.9"
            }
        ],
        "technical_skills": {
            "languages": ["Python", "Go"]
        },
        "work_experience": [],
        "projects": [],
        "certifications": [],
        "achievements": []
    }

    response = client.post("/api/v1/intake/structured", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "stored"
    assert res_data["resume_version_id"] is not None
    assert res_data["target_role"] == "Backend Engineer"


def test_check_ats_threshold_routing_opt_out() -> None:
    state: AgentState = {
        "session_id": "session-test-opt-out",
        "user_id": 1,
        "resume_text": "Original raw text",
        "job_description": "Sample JD",
        "ats_score": 0.50,
        "intake_mode": "upload",
        "approve_optimization": False,
    }
    
    updated_state = check_ats_threshold(state)
    assert updated_state["optimization_recommended"] is False
    
    route = check_ats_threshold_routing(state)
    assert route == "dispatch"


def test_download_original_file_opt_out() -> None:
    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.api.dependencies import get_db
    
    client = TestClient(app)
    db = next(get_db())
    
    from src.database.models import User, ResumeVersion, WorkflowSession
    
    user = User(email="optout@test.com", full_name="Opt Out Test")
    db.add(user)
    db.flush()
    
    from pathlib import Path
    # Save a fake original file
    upload_dir = Path("storage_workspace/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    fake_orig_path = upload_dir / f"user_{user.id}_original.pdf"
    fake_orig_path.write_bytes(b"pdf contents")
    
    resume_version = ResumeVersion(
        user_id=user.id,
        version_label="test-optout",
        raw_text="Fake resume",
        metadata_json={
            "approve_optimization": False,
            "stored_path": str(fake_orig_path)
        }
    )
    db.add(resume_version)
    db.flush()
    
    session = WorkflowSession(
        id="session-optout-fake",
        user_id=user.id,
        resume_version_id=resume_version.id,
        status="draft_ready_for_human_review",
        state_json={"approve_optimization": False}
    )
    db.add(session)
    db.commit()
    
    # Request download
    resp = client.get(f"/api/v1/resume/download/{user.id}/{resume_version.id}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content == b"pdf contents"
    
    # Clean up DB
    db.delete(session)
    db.delete(resume_version)
    db.delete(user)
    db.commit()
    
    # Remove fake file
    if fake_orig_path.exists():
        fake_orig_path.unlink()


@pytest.mark.anyio
async def test_evaluate_initial_ats_node() -> None:
    from src.workflow.graph import evaluate_initial_ats
    from src.workflow.state import AgentState
    from unittest.mock import AsyncMock, patch
    
    rich_resume = (
        "John Doe\njohn.doe@example.com | 555-555-5555 | San Francisco, CA\n"
        "github.com/johndoe\n\n"
        "EDUCATION\n"
        "---\n"
        "Bachelor of Science | Stanford University | Stanford, CA | June 2022 | GPA: 3.8\n\n"
        "EXPERIENCE\n"
        "---\n"
        "Software Engineer | Tech Corp | San Francisco, CA | June 2022 - Present\n"
        "• Developed and optimized high-performance FastAPI backend services processing millions of daily queries.\n"
        "• Orchestrated CI/CD deployment pipelines on AWS using Docker, reducing delivery cycles by 30%.\n"
        "• Optimized PostgreSQL database indexing and queries, decreasing average response time by 40%.\n"
        "• Collaborated with cross-functional product teams to design and document scalable software architectures.\n"
        "• Participated in agile sprint ceremonies, planning, and code review sessions to maintain code quality standards.\n"
        "• Automated unit and integration testing workflows, increasing test coverage across core packages by 25%.\n"
        "• Mentored junior engineers, assisting with technical onboarding and explaining engineering design patterns.\n\n"
        "ACHIEVEMENTS\n"
        "---\n"
        "• Won first place in the Stanford Hackathon 2021 for designing an AI-driven personal job assistant application.\n"
        "• Published an open-source library for automated API validation, garnering over 500 stars on GitHub.\n"
        "• Ranked in the top 1% of competitive programmers on LeetCode with a rating of 2200.\n\n"
        "SKILLS\n"
        "---\n"
        "Languages: Python, Go, SQL, Javascript\n"
        "Tools: Git, Docker, Kubernetes, AWS\n"
        "Libraries: FastAPI, React, Node.js, SQLAlchemy\n"
    )
    state: AgentState = {
        "session_id": "session-ats-test",
        "user_id": 1,
        "resume_text": rich_resume,
        "job_description": "We need a python developer with fastapi experience",
        "intake_mode": "upload",
    }
    
    with patch("src.agents.ats_engine.ATSEngine.combined_score", new_callable=AsyncMock) as mock_score:
        from src.agents.ats_engine import ATSScore
        mock_score.return_value = ATSScore(score=0.75, details={}, method="mock")
        
        with patch("langgraph.types.interrupt") as mock_interrupt:
            mock_interrupt.return_value = True
            
            result = await evaluate_initial_ats(state)
            assert result["ats_score"] == 75.0
            assert result["needs_optimization_approval"] is False
            assert result["approve_optimization"] is True


def test_initial_ats_routing() -> None:
    from src.workflow.graph import initial_ats_routing
    from src.workflow.state import AgentState
    
    # 1. build_from_scratch -> optimize
    state1: AgentState = {"intake_mode": "build_from_scratch"}
    assert initial_ats_routing(state1) == "optimize"
    
    # 2. approve_optimization is False -> dispatch
    state2: AgentState = {"intake_mode": "upload", "approve_optimization": False}
    assert initial_ats_routing(state2) == "dispatch"
    
    # 3. approve_optimization is True -> optimize
    state3: AgentState = {"intake_mode": "upload", "approve_optimization": True}
    assert initial_ats_routing(state3) == "optimize"


def test_hitl_decision_route_not_found() -> None:
    from fastapi.testclient import TestClient
    from src.api.main import app
    client = TestClient(app)
    
    response = client.post(
        "/api/v1/hitl/decision",
        json={"thread_id": "non-existent-session-id", "approve_optimization": True}
    )
    assert response.status_code == 404


def test_validate_resume_info_density_full() -> None:
    from src.schemas.resume import validate_resume_info_density
    
    sparse_data = {
        "education": [],
        "technical_skills": {},
        "work_experience": []
    }
    has_info, missing = validate_resume_info_density(sparse_data)
    assert not has_info
    assert "Work Experience bullets count is less than 3" in missing
    assert "Education section is missing" in missing
    assert "Skills section is empty or missing" in missing
    assert "Total word count is 0 (minimum required: 150)" in missing

    rich_data = {
        "education": [{
            "degree": "Bachelor of Science in Computer Science and Engineering",
            "institution": "Stanford University in Stanford, California",
            "graduation_year": "2022"
        }],
        "technical_skills": {
            "programming_languages": ["Python", "JavaScript", "Go", "Rust", "C++", "HTML", "CSS", "SQL"],
            "frameworks": ["FastAPI", "React", "Node.js", "Django", "Flask", "Tailwind CSS", "Bootstrap"],
            "databases": ["PostgreSQL", "MongoDB", "Redis", "MySQL", "Cassandra", "Elasticsearch"],
            "cloud_tools": ["AWS", "Docker", "Kubernetes", "Google Cloud Platform", "Terraform", "Jenkins"]
        },
        "work_experience": [
            {
                "company": "Tech Corporation International Inc.",
                "role": "Lead Backend Software Engineer",
                "bullets": [
                    "Developed and maintained highly scalable and distributed FastAPI microservices processing millions of API requests daily with minimal latency.",
                    "Engineered robust and reliable continuous integration and continuous delivery (CI/CD) pipelines automating software deployments to production.",
                    "Optimized complex PostgreSQL database queries and schema designs, reducing search times and query performance latency by over 40 percent.",
                    "Collaborated closely with cross-functional teams including product management and design to deliver high-quality software features on schedule."
                ]
            },
            {
                "company": "Startup Labs LLC",
                "role": "Full Stack Developer",
                "bullets": [
                    "Designed and implemented responsive frontend user interfaces using React and Tailwind CSS, increasing user engagement metrics.",
                    "Built secure user authentication and authorization systems using OAuth2 and JSON Web Tokens (JWT) for secure API endpoints.",
                    "Maintained server configurations and deployed updates to Amazon Web Services (AWS) EC2 instances using Docker containerization."
                ]
            }
        ],
        "professional_summary": "Highly motivated, results-oriented Python and Full Stack Software Engineer with over 4 years of professional experience building scalable web applications. Expert in backend microservices architectures using FastAPI and frontend modern frameworks like React. Proven track record of improving database performance, optimizing deployment pipelines, and collaborating with global teams."
    }
    has_info2, missing2 = validate_resume_info_density(rich_data)
    assert has_info2
    assert len(missing2) == 0


@pytest.mark.anyio
async def test_evaluate_initial_ats_insufficient_data() -> None:
    from src.workflow.graph import evaluate_initial_ats
    from src.workflow.state import AgentState
    from unittest.mock import AsyncMock, patch
    
    state: AgentState = {
        "session_id": "session-ats-sparse-test",
        "user_id": 1,
        "resume_text": "Sparse candidate resume with low content.",
        "job_description": "We need a highly skilled software engineer with extensive deep learning experience.",
        "intake_mode": "upload",
    }
    
    with patch("src.agents.ats_engine.ATSEngine.combined_score", new_callable=AsyncMock) as mock_score:
        from src.agents.ats_engine import ATSScore
        mock_score.return_value = ATSScore(score=0.55, details={}, method="mock")
        
        with patch("langgraph.types.interrupt") as mock_interrupt:
            mock_interrupt.return_value = "switch_to_scratch"
            
            result = await evaluate_initial_ats(state)
            assert abs(result["ats_score"] - 55.0) < 0.1
            assert result["recommendation"] == "switch_to_scratch_build"
            assert result["intake_mode"] == "build_from_scratch"


@pytest.mark.anyio
async def test_evaluate_initial_ats_node_raises_value_error_on_invalid_optimization() -> None:
    from src.workflow.graph import evaluate_initial_ats
    from src.workflow.state import AgentState
    from unittest.mock import AsyncMock, patch
    
    state: AgentState = {
        "session_id": "session-ats-test-fail",
        "user_id": 1,
        "resume_text": "Sparse candidate resume with low content.",
        "job_description": "We need a highly skilled software engineer with extensive deep learning experience.",
        "intake_mode": "upload",
    }
    
    with patch("src.agents.ats_engine.ATSEngine.combined_score", new_callable=AsyncMock) as mock_score:
        from src.agents.ats_engine import ATSScore
        mock_score.return_value = ATSScore(score=0.55, details={}, method="mock")
        
        with patch("langgraph.types.interrupt") as mock_interrupt:
            mock_interrupt.return_value = "optimize"
            
            with pytest.raises(ValueError) as excinfo:
                await evaluate_initial_ats(state)
            assert "Cannot optimize resume with ATS score < 80%" in str(excinfo.value)


def test_hitl_decision_blocks_optimize_on_invalid() -> None:
    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.api.dependencies import get_db
    from src.database.models import User, ResumeVersion, WorkflowSession
    
    client = TestClient(app)
    db = next(get_db())
    
    user = User(email="test_block_opt@test.com", full_name="Block Opt Test")
    db.add(user)
    db.flush()
    
    resume_version = ResumeVersion(
        user_id=user.id,
        version_label="test-block-opt",
        raw_text="Sparse candidate resume with low content.",
        ats_score=55.0,
    )
    db.add(resume_version)
    db.flush()
    
    session = WorkflowSession(
        id="session-block-opt-fake",
        user_id=user.id,
        resume_version_id=resume_version.id,
        status="PAUSED_FOR_HUMAN_OPTIMIZATION_APPROVAL",
        state_json={
            "intake_mode": "upload",
            "ats_score": 55.0,
            "resume_text": "Sparse candidate resume with low content.",
        }
    )
    db.add(session)
    db.commit()
    
    try:
        response = client.post(
            "/api/v1/hitl/decision",
            json={
                "thread_id": "session-block-opt-fake",
                "action": "optimize"
            }
        )
        assert response.status_code == 400
        assert "insufficient information" in response.json()["detail"].lower()
    finally:
        db.delete(session)
        db.delete(resume_version)
        db.delete(user)
        db.commit()


def test_resume_optimization_decision_blocks_optimize_on_invalid() -> None:
    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.api.dependencies import get_db
    from src.database.models import User, ResumeVersion, WorkflowSession, JobTarget
    
    client = TestClient(app)
    db = next(get_db())
    
    user = User(email="test_block_opt2@test.com", full_name="Block Opt Test 2")
    db.add(user)
    db.flush()
    
    resume_version = ResumeVersion(
        user_id=user.id,
        version_label="test-block-opt-2",
        raw_text="Sparse candidate resume with low content.",
        ats_score=55.0,
    )
    db.add(resume_version)
    db.flush()
    
    job_target = JobTarget(
        user_id=user.id,
        role_title="Software Engineer",
        company_name="Acme Corp",
        job_description="We need a python dev",
    )
    db.add(job_target)
    db.flush()
    
    session = WorkflowSession(
        id="session-block-opt-fake-2",
        user_id=user.id,
        resume_version_id=resume_version.id,
        job_target_id=job_target.id,
        status="PAUSED_FOR_HUMAN_OPTIMIZATION_APPROVAL",
        state_json={
            "intake_mode": "upload",
            "ats_score": 55.0,
            "resume_text": "Sparse candidate resume with low content.",
        }
    )
    db.add(session)
    db.commit()
    
    try:
        response = client.post(
            "/api/v1/hitl/resume-optimization-decision",
            json={
                "user_id": user.id,
                "job_id": str(job_target.id),
                "action": "optimize"
            }
        )
        assert response.status_code == 400
        assert "insufficient information" in response.json()["detail"].lower()
    finally:
        db.delete(session)
        db.delete(job_target)
        db.delete(resume_version)
        db.delete(user)
        db.commit()


@pytest.mark.anyio
async def test_manual_optimize_draft_blocks_optimize_on_invalid() -> None:
    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.api.dependencies import get_db
    from src.database.models import User, ResumeVersion, JobTarget
    from unittest.mock import AsyncMock, patch
    
    client = TestClient(app)
    db = next(get_db())
    
    user = User(email="test_block_opt3@test.com", full_name="Block Opt Test 3")
    db.add(user)
    db.flush()
    
    resume_version = ResumeVersion(
        user_id=user.id,
        version_label="test-block-opt-3",
        raw_text="Sparse candidate resume with low content.",
        ats_score=55.0,
    )
    db.add(resume_version)
    db.flush()
    
    job_target = JobTarget(
        user_id=user.id,
        role_title="Software Engineer",
        company_name="Acme Corp",
        job_description="We need a python dev",
    )
    db.add(job_target)
    db.commit()
    
    try:
        from src.agents.ats_engine import ATSScore
        with patch("src.agents.ats_engine.ATSEngine.combined_score", new_callable=AsyncMock) as mock_score:
            mock_score.return_value = ATSScore(score=0.55, details={}, method="mock")
            
            response = client.post(
                "/api/v1/workflow/manual-optimize-draft",
                json={
                    "resume_version_id": resume_version.id,
                    "job_target_id": job_target.id,
                    "intake_mode": "upload"
                }
            )
            assert response.status_code == 400
            assert "insufficient information" in response.json()["detail"].lower()
    finally:
        db.delete(job_target)
        db.delete(resume_version)
        db.delete(user)
        db.commit()
