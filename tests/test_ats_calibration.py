# File: tests/test_ats_calibration.py
import pytest
from src.agents.ats_engine import ATSEngine
from src.config.constants import WEAK_VERBS_REGEX, METRIC_PATTERNS_REGEX
from src.utils.docx_compiler import clean_resume_syntax
from src.agents.optimizer import ResumeOptimizer


def test_weak_verbs_regex_detection():
    """Verify WEAK_VERBS_REGEX catches weak/passive verbs."""
    sample = "Assisted with database migration and helped to optimize API queries. Responsible for system monitoring."
    matches = WEAK_VERBS_REGEX.findall(sample)
    assert len(matches) >= 3
    assert any("assisted" in m.lower() for m in matches)
    assert any("helped" in m.lower() for m in matches)
    assert any("responsible for" in m.lower() for m in matches)


def test_metric_patterns_regex_detection():
    """Verify METRIC_PATTERNS_REGEX catches quantified metrics ($50k, 30%, 2x, 100+)."""
    sample1 = "Improved API throughput by 35% and reduced latency 2x."
    sample2 = "Managed budget of $50,000 serving 100+ active enterprise clients."
    
    assert len(METRIC_PATTERNS_REGEX.findall(sample1)) >= 2
    assert len(METRIC_PATTERNS_REGEX.findall(sample2)) >= 2


@pytest.mark.asyncio
async def test_ats_engine_penalty_calibration_and_feedback():
    """Verify penalty scoring calibrates scores to realistic Resume Worded range (~40-65%) and generates actionable feedback."""
    engine = ATSEngine()
    
    # Resume with passive verbs, missing metrics, and missing skills
    unoptimized_resume = """
    John Doe
    Developer

    Experience:
    - Assisted with backend development and helped to write SQL queries.
    - Responsible for bug fixes and worked on team tasks.
    - Handled customer support tickets.
    """
    
    job_description = """
    We are seeking a Senior Backend Engineer proficient in Python, FastAPI, Docker, Kubernetes, PostgreSQL, and Redis.
    Must spearhead microservices architecture and optimize database performance.
    """

    res = engine.calculate_ats_score(unoptimized_resume, job_description)
    score = res["ats_score"]
    
    # Verify score is calibrated strictly (Resume Worded benchmark ~40-65% range, not inflated to 80%+)
    assert score <= 65
    assert "penalties" in res
    assert res["penalties"]["impact_verbs"] > 0
    assert res["penalties"]["metrics"] > 0
    
    # Verify 3-4 line actionable feedback is generated
    feedback = res.get("actionable_feedback", "")
    assert len(feedback.splitlines()) >= 2
    assert "Technical Skills Gap" in feedback or "Action Verb Impact" in feedback


def test_clean_resume_syntax_strips_markdown_and_emdashes():
    """Verify clean_resume_syntax strips ** bolding and replaces em-dashes — with hyphens -."""
    raw = "**Senior Software Engineer** — TechCorp Solutions — **Python** & FastAPI"
    cleaned = clean_resume_syntax(raw)
    assert "**" not in cleaned
    assert "—" not in cleaned
    assert "-" in cleaned
    assert "Senior Software Engineer - TechCorp Solutions - Python & FastAPI" in cleaned


def test_optimizer_clean_syntax():
    """Verify ResumeOptimizer.clean_syntax cleans markdown artifacts."""
    optimizer = ResumeOptimizer()
    text = "**Led development** of microservices — improved scalability by 40%."
    cleaned = optimizer.clean_syntax(text)
    assert "**" not in cleaned
    assert "—" not in cleaned
    assert "-" in cleaned
