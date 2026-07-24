# File: tests/test_router.py
from __future__ import annotations

from src.agents.router import ModelTier, TaskComplexityRouter


def test_router_selects_small_model_for_simple_prompt() -> None:
    router = TaskComplexityRouter(complexity_threshold=0.65)
    decision = router.select_model("Summarize this short resume.")
    assert decision.model_tier is ModelTier.SMALL


def test_router_selects_large_model_for_complex_prompt() -> None:
    router = TaskComplexityRouter(complexity_threshold=0.2)
    decision = router.select_model(
        "Analyze and optimize this resume against the target role.",
        context={"job_description": "Python platform architect role"},
    )
    assert decision.model_tier is ModelTier.LARGE
