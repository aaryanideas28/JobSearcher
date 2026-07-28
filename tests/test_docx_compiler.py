# File: tests/test_docx_compiler.py
"""Tests for Word Document compiler logic."""

from __future__ import annotations

from pathlib import Path
from src.utils.docx_compiler import DocxCompiler


def test_render_official_ats_docx() -> None:
    compiler = DocxCompiler()
    candidate_data = {
        "contact": {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "123-456-7890",
            "location": "San Francisco, CA",
            "github": "github.com/test",
            "linkedin": "linkedin.com/in/test"
        },
        "summary": "Experienced testing engineer",
        "skills": ["Python", "Pytest", "Word"],
        "experience": [
            {
                "company": "QA Corp",
                "role": "Test Lead",
                "start_date": "2020",
                "end_date": "2023",
                "description": "- Tested code.\n- Wrote scripts."
            }
        ],
        "projects": [
            {
                "name": "Test Tool",
                "description": "- Automated testing.\n- Created reports."
            }
        ],
        "education": [
            {
                "institution": "State University",
                "degree": "B.S. Computer Science",
                "start_date": "2016",
                "end_date": "2020"
            }
        ]
    }
    
    doc_path = compiler.render_official_ats_docx(candidate_data, user_id=99, version=1)
    path = Path(doc_path)
    assert path.exists()
    assert "user_99" in str(path)
    assert "resume_v1.docx" in str(path)


def test_compile_agent_state() -> None:
    compiler = DocxCompiler()
    state = {
        "user_id": 42,
        "attempt_count": 3,
        "optimized_resume_json": {
            "contact": {"name": "State User", "email": "state@example.com"},
            "summary": "Expert dev",
            "skills": ["Python"],
            "experience": []
        }
    }
    docx_path = compiler.compile_agent_state(state, "resume")
    assert "final_documents" in str(docx_path)
    assert "user_42" in str(docx_path)
    assert "resume_v3.docx" in str(docx_path)
    assert docx_path.exists()


def test_compile_docx_cover_letter() -> None:
    compiler = DocxCompiler()
    state = {
        "metadata": {"candidate_name": "Cover Letter User"},
        "cover_letter": "Dear Recruiter, this is a test cover letter.",
        "session_id": "test_session_123"
    }
    docx_path = compiler.compile_agent_state(state, "cover_letter")
    assert "generated" in str(docx_path)
    assert "cover_letter_test_session_123.docx" in str(docx_path)
    assert docx_path.exists()
