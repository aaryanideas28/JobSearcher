# File: src/agents/router.py
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ModelTier(StrEnum):
    """Supported local model tiers."""

    SMALL = "1.5b"
    LARGE = "8b"


@dataclass(slots=True)
class RoutingDecision:
    """Decision object returned by the task complexity router."""

    model_tier: ModelTier
    model_name: str
    reason: str
    estimated_complexity: float


class TaskComplexityRouter:
    """Select a small or large model based on task complexity signals."""

    def __init__(
        self,
        small_model_name: str = "llama3.2:1b",
        large_model_name: str = "llama3.1:8b",
        complexity_threshold: float = 0.65,
    ) -> None:
        self.small_model_name = small_model_name
        self.large_model_name = large_model_name
        self.complexity_threshold = complexity_threshold

    def estimate_complexity(self, prompt: str, context: dict[str, object] | None = None) -> float:
        """Estimate task complexity using lightweight lexical and metadata features."""

        context = context or {}
        token_count = len(prompt.split())
        has_job_description = bool(context.get("job_description"))
        has_multi_step_instruction = any(marker in prompt.lower() for marker in ("compare", "optimize", "rewrite", "analyze"))
        raw_score = min(1.0, (token_count / 600.0) + (0.25 if has_job_description else 0.0) + (0.2 if has_multi_step_instruction else 0.0))
        return round(raw_score, 3)

    def select_model(self, prompt: str, context: dict[str, object] | None = None) -> RoutingDecision:
        """Return a routing decision for the given prompt and optional context."""

        complexity = self.estimate_complexity(prompt, context)
        if complexity >= self.complexity_threshold:
            return RoutingDecision(ModelTier.LARGE, self.large_model_name, "complex_task", complexity)
        return RoutingDecision(ModelTier.SMALL, self.small_model_name, "simple_task", complexity)
