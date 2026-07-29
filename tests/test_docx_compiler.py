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


def test_parse_resume_text_to_dict() -> None:
    compiler = DocxCompiler()
    raw_text = (
        "Abhishek Sharma\n"
        "AI/ML & Python Developer\n"
        "shabhishek055@gmail.com | +91 9575676062 | Indore, India | linkedin.com/in/Abhishek\n\n"
        "---\n"
        "PROFILE SUMMARY\n"
        "---\n"
        "Results-driven AI/ML Engineer with a proven track record.\n\n"
        "---\n"
        "EDUCATION\n"
        "---\n"
        "Bachelor of Technology (IT Engineering) | Rajiv Gandhi Prodhogiki Vishvvidhyalya, Bhopal | Indore | 2020-2024 | 7.6 CGPA\n\n"
        "---\n"
        "PROJECTS\n"
        "---\n"
        "TechnikalPAI - A Behavior-Based Friendly AI | Open-AI, Flask | 04/2024 - present\n"
        "• Developed behavior-based Friendly AI.\n"
        "• Achieved 85% accuracy.\n\n"
        "---\n"
        "SKILLS\n"
        "---\n"
        "Languages: Python, SQL, R\n"
        "ML Frameworks: TensorFlow, PyTorch"
    )
    
    parsed = compiler.parse_resume_text_to_dict(raw_text)
    assert parsed["contact"]["name"] == "Abhishek Sharma"
    assert parsed["subtitle"] == "AI/ML & Python Developer"
    assert parsed["contact"]["email"] == "shabhishek055@gmail.com"
    assert parsed["contact"]["phone"] == "+91 9575676062"
    assert len(parsed["education"]) == 1
    assert parsed["education"][0]["degree"] == "Bachelor of Technology (IT Engineering)"
    assert len(parsed["projects"]) == 1
    assert parsed["projects"][0]["name"] == "TechnikalPAI - A Behavior-Based Friendly AI"
    assert len(parsed["projects"][0]["bullets"]) == 2
    assert len(parsed["skills"]) == 2
    assert parsed["skills"][0]["category"] == "Languages"

