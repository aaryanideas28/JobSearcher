# File: tests/test_ats_engine.py
from __future__ import annotations

import asyncio
from src.agents.ats_engine import ATSEngine, ATSScore


def test_calculate_ats_score_output_structure() -> None:
    engine = ATSEngine()
    resume = "Jane Doe\nPython Software Engineer with experience in FastAPI, PostgreSQL, and Docker."
    jd = "Seeking a Senior Backend Engineer proficient in Python, FastAPI, Kubernetes, and AWS."

    result = engine.calculate_ats_score(resume, jd)

    assert isinstance(result, dict)
    assert "overall_score" in result
    assert "missing_keywords" in result
    assert "semantic_gaps" in result

    assert isinstance(result["overall_score"], float)
    assert 0.0 <= result["overall_score"] <= 1.0
    assert isinstance(result["missing_keywords"], list)
    assert isinstance(result["semantic_gaps"], list)

    for gap in result["semantic_gaps"]:
        assert "requirement" in gap
        assert "similarity" in gap
        assert isinstance(gap["similarity"], float)


def test_combined_score_returns_ats_score() -> None:
    engine = ATSEngine()
    resume = "Experienced Developer with Python, SQL, Git."
    jd = "Software Developer with Python, SQL, Docker, CI/CD experience."

    score = asyncio.run(engine.combined_score(resume, jd))

    assert isinstance(score, ATSScore)
    assert isinstance(score.score, float)
    assert 0.0 <= score.score <= 1.0
    assert score["overall_score"] == score.score
    assert "missing_keywords" in score.details
    assert "semantic_gaps" in score.details


def test_ats_engine_calibrated_scoring() -> None:
    engine = ATSEngine()
    
    # 1. Relevant resume with matching skills (should score in 75% to 95% range)
    resume = "Senior Engineer with Python, FastAPI, Docker, and PostgreSQL experience."
    jd = "Seeking a developer proficient in Python, FastAPI, Docker, and Kubernetes."
    
    result = engine.calculate_ats_score(resume, jd)
    
    assert "ats_score" in result
    assert "matched_skills" in result
    assert "missing_skills" in result
    assert isinstance(result["ats_score"], int)
    
    # Python, FastAPI, Docker matched; Kubernetes missing. (3 out of 4 matched)
    assert "python" in result["matched_skills"]
    assert "fastapi" in result["matched_skills"]
    assert "docker" in result["matched_skills"]
    assert "kubernetes" in result["missing_skills"]
    
    # Must reliably score in 75% to 95% range
    assert 75 <= result["ats_score"] <= 95
    
    # 2. No matching skills (should score below 50%)
    irrelevant_resume = "Chef specializing in Italian cuisine and pastry arts."
    irrelevant_result = engine.calculate_ats_score(irrelevant_resume, jd)
    assert irrelevant_result["ats_score"] < 50

