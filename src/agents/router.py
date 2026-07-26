# File: src/agents/router.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from config.settings import get_settings
from src.workflow.state import AgentState


class ModelTier(str, Enum):
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
        small_model_name: str | None = None,
        large_model_name: str | None = None,
        complexity_threshold: float = 0.65,
    ) -> None:
        settings = get_settings()
        self.small_model_name = small_model_name or settings.ollama_small_model
        # LLM_MODEL_NAME is the configured high-capability local model.
        self.large_model_name = large_model_name or settings.llm_model_name
        self.complexity_threshold = complexity_threshold

    def estimate_complexity(self, prompt: str, context: dict[str, object] | None = None) -> float:
        """Estimate task complexity using lightweight lexical and metadata features."""

        context = context or {}
        token_count = len(prompt.split())
        has_job_description = bool(context.get("job_description"))
        complex_markers = ("compare", "optimize", "rewrite", "analyze", "cover letter", "tailor", "application")
        has_multi_step_instruction = any(marker in prompt.lower() for marker in complex_markers)
        raw_score = min(1.0, (token_count / 600.0) + (0.25 if has_job_description else 0.0) + (0.2 if has_multi_step_instruction else 0.0))
        return round(raw_score, 3)

    def select_model(self, prompt: str, context: dict[str, object] | None = None) -> RoutingDecision:
        """Return a routing decision for the given prompt and optional context."""

        complexity = self.estimate_complexity(prompt, context)
        if complexity >= self.complexity_threshold:
            return RoutingDecision(ModelTier.LARGE, self.large_model_name, "complex_task", complexity)
        return RoutingDecision(ModelTier.SMALL, self.small_model_name, "simple_task", complexity)

    async def route(self, state: AgentState) -> AgentState:
        """Store an async routing decision in the shared workflow state."""

        prompt = str(state.metadata.get("request", state.job_description or state.resume_text))
        decision = self.select_model(prompt, {"job_description": state.job_description})
        state.metadata["routing"] = {
            "model_tier": decision.model_tier.value,
            "model_name": decision.model_name,
            "reason": decision.reason,
            "estimated_complexity": decision.estimated_complexity,
        }
        return state
