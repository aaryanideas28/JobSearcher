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


def test_router_quantized_tags() -> None:
    router = TaskComplexityRouter(
        small_model_name="qwen2.5:3b",
        large_model_name="llama3.1:8b-instruct-q4_K_M",
        complexity_threshold=0.1
    )
    decision = router.select_model("Perform complex resume editing for platform architect.")
    assert decision.model_name == "llama3.1:8b-instruct-q4_K_M"
    assert decision.model_tier is ModelTier.LARGE
