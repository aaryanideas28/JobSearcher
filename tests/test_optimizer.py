# File: tests/test_optimizer.py
from __future__ import annotations

import asyncio
from src.agents.ats_engine import ATSEngine
from src.agents.optimizer import OptimizationResult, ResumeOptimizer


def test_optimizer_proves_20_percent_ats_score_improvement() -> None:
    optimizer = ResumeOptimizer()
    ats_engine = ATSEngine()

    weak_resume = (
        "Alice Smith\n"
        "Software Engineer at TechCorp from 2019 to 2022.\n"
        "Worked on simple web applications and basic bug fixes."
    )

    job_description = (
        "Target Role: Senior Backend Engineer\n"
        "Requirements:\n"
        "• Build scalable microservices using Python, FastAPI, and PostgreSQL.\n"
        "• Experience with Docker containerization and Kubernetes orchestration.\n"
        "• Implement CI/CD pipelines and cloud infrastructure on AWS."
    )

    # 1. Baseline ATS score before optimization
    baseline_score_obj = asyncio.run(ats_engine.combined_score(weak_resume, job_description))
    old_score = baseline_score_obj.score

    # 2. Run optimization with ATS feedback loop
    opt_result = asyncio.run(
        optimizer.optimize_resume(
            resume_text=weak_resume,
            job_description=job_description,
            skills_to_highlight=["Python", "FastAPI", "Docker", "AWS"],
            target_role="Senior Backend Engineer",
        )
    )

    # 3. New ATS score after optimization
    new_score_obj = asyncio.run(ats_engine.combined_score(opt_result.optimized_resume, job_description))
    new_score = new_score_obj.score

    # 4. Assert 20% relative ATS score improvement: new_score >= (old_score * 1.20)
    assert old_score > 0.0
    relative_improvement = (new_score - old_score) / old_score
    assert new_score >= (old_score * 1.20), (
        f"Expected >= 20% relative improvement, got {relative_improvement * 100:.2f}% "
        f"(old: {old_score:.4f}, new: {new_score:.4f})"
    )


def test_optimizer_preserves_locked_entities() -> None:
    optimizer = ResumeOptimizer()

    resume_text = (
        "Johnathan Vance\n"
        "Senior Systems Architect\n"
        "Worked at Acme Systems Inc. from 2018 to 2023 leading database migration."
    )
    locked = optimizer.extract_locked_entities(resume_text)

    assert "2018" in locked["years"]
    assert "2023" in locked["years"]

    opt_result = asyncio.run(
        optimizer.optimize_resume(
            resume_text=resume_text,
            job_description="Seeking a Systems Architect proficient in Linux, Go, and Distributed Systems.",
        )
    )

    # Assert entities preserved in optimized resume text
    for year in locked["years"]:
        assert year in opt_result.optimized_resume
    for company in locked["companies"]:
        assert company in opt_result.optimized_resume
    for name in locked["names"]:
        assert name in opt_result.optimized_resume


def test_optimizer_enforces_1_page_length_limit() -> None:
    optimizer = ResumeOptimizer()

    long_resume = "John Doe\nSoftware Engineer 2021.\n" + ("Built large scale microservices with Python and FastAPI.\n" * 100)
    assert len(long_resume) > 3500

    opt_result = asyncio.run(
        optimizer.optimize_resume(
            resume_text=long_resume,
            job_description="Python Backend Engineer role requiring FastAPI and PostgreSQL.",
        )
    )

    assert len(opt_result.optimized_resume) <= 3500
