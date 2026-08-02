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
    
    resume = """
    Senior Engineer
    
    Professional Experience:
    - Engineered high-throughput microservices using Python and FastAPI, increasing API response speed by 35%.
    - Containerized application services using Docker and managed PostgreSQL databases serving 100+ enterprise clients.
    - Spearheaded backend refactoring and automated test suites achieving 90% code coverage.
    - Improved deployment reliability and system uptime to 99.9%.
    """
    jd = "Seeking a developer proficient in Python, FastAPI, Docker, and Kubernetes."
    
    result = engine.calculate_ats_score(resume, jd)
    
    assert "ats_score" in result
    assert "matched_skills" in result
    assert "missing_skills" in result
    assert isinstance(result["ats_score"], int)
    
    assert "python" in result["matched_skills"]
    assert "fastapi" in result["matched_skills"]
    assert "docker" in result["matched_skills"]
    assert "kubernetes" in result["missing_skills"]
    
    assert 30 <= result["ats_score"] <= 85
    
    # 2. No matching skills (should score below 50%)
    irrelevant_resume = "Chef specializing in Italian cuisine and pastry arts."
    irrelevant_result = engine.calculate_ats_score(irrelevant_resume, jd)
    assert irrelevant_result["ats_score"] < 50


def test_skill_aliases_are_canonically_matched() -> None:
    engine = ATSEngine()
    result = engine.calculate_ats_score(
        "Backend engineer with Kubernetes, Node.js, and machine learning experience.",
        "Required: k8s, nodejs, and ML experience.",
    )

    assert "kubernetes" in result["matched_skills"]
    assert "node.js" in result["matched_skills"]
    assert "machine learning" in result["matched_skills"]
    assert not result["missing_skills"]


def test_structure_signals_are_diagnostic_not_hard_failures() -> None:
    engine = ATSEngine()
    result = engine.calculate_ats_score(
        "Jane Doe\nEmail: jane@example.com\nSkills\nPython",
        "Python developer",
    )

    assert result["overall_score"] > 0
    assert result["structure"]["contact"]["email_detected"] is True
    assert "experience" in result["structure"]["missing_headings"]
    assert isinstance(result["structure"]["parse_warnings"], list)


def test_required_and_preferred_skills_are_reported_separately() -> None:
    engine = ATSEngine()
    result = engine.calculate_ats_score(
        "Backend engineer with Python experience.",
        "Required: Python. Preferred: Kubernetes.",
    )

    assert result["required_skills"] == ["python"]
    assert result["preferred_skills"] == ["kubernetes"]
    assert result["matched_required_skills"] == ["python"]
    assert result["matched_preferred_skills"] == []


def test_calculate_score_returns_isolated_cached_results() -> None:
    engine = ATSEngine()
    first = engine.calculate_ats_score("Python engineer", "Python developer")
    first["matched_skills"].clear()
    second = engine.calculate_ats_score("Python engineer", "Python developer")

    assert second["matched_skills"] == ["python"]


def test_improvement_advice_is_grounded_and_does_not_invent_metrics() -> None:
    engine = ATSEngine()
    result = engine.calculate_ats_score(
        "Developer\n- Worked on backend tasks without quantified outcomes.",
        "Required: Python. Preferred: Kubernetes.",
    )

    advice_text = " ".join(item["suggestion"] for item in result["improvement_advice"])
    assert "Python" in advice_text
    assert "Never invent metrics" in advice_text
    assert "30%" not in advice_text

    metric_fix = next(
        item for item in result["quick_fixes"] if item["penalty_type"] == "metrics"
    )
    assert metric_fix["requires_user_value"] is True
    assert "30%" not in metric_fix["suggestion"]


def test_match_explanation_has_demo_schema() -> None:
    engine = ATSEngine()
    result = engine.calculate_ats_score(
        "Jane Doe\nEmail: jane@example.com\nSkills\nPython\nExperience\n- Built APIs.",
        "Required: Python. Backend developer role.",
    )

    explanation = result["match_explanation"]
    assert explanation["match_score"] == result["ats_score"]
    assert set(explanation["radar_chart"]) == {
        "content",
        "skills",
        "sections",
        "style",
        "format",
    }
    assert len(explanation["highlights"]) == 3
    assert len(explanation["improvements"]) == 3
    assert all(0 <= value <= 100 for value in explanation["radar_chart"].values())


def test_match_explanation_categories_reflect_detected_structure() -> None:
    engine = ATSEngine()
    result = engine.calculate_ats_score(
        "Jane Doe\nEmail: jane@example.com\nPython developer",
        "Python developer",
    )

    radar = result["match_explanation"]["radar_chart"]
    assert radar["sections"] < 100
    assert radar["skills"] == 100

