# File: src/agents/router.py
"""Cost and task complexity router for selecting local Ollama model tiers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.config.settings import get_settings


class ModelTier(StrEnum):
    """Supported model tiers."""

    SMALL = "1.5b"
    LARGE = "8b"
    LIGHTWEIGHT = "1.5b"
    MAIN = "8b"
    QWEN_3B = "qwen2.5:3b"
    LLAMA_8B_Q4 = "llama3.1:8b-instruct-q4_K_M"


@dataclass(slots=True)
class RoutingDecision:
    """Structured routing decision returned by the router."""

    model_tier: ModelTier
    model_name: str
    reason: str
    estimated_complexity: float


class TaskComplexityRouter:
    """Select a lightweight or main LLM based on prompt complexity."""

    def __init__(
        self,
        small_model_name: str | None = None,
        large_model_name: str | None = None,
        complexity_threshold: float = 0.65,
    ) -> None:
        settings = get_settings()
        self.small_model_name = small_model_name or settings.ollama_small_model
        self.large_model_name = large_model_name or settings.ollama_large_model
        self.complexity_threshold = complexity_threshold

    def estimate_complexity(self, task_text: str) -> float:
        """Estimate task complexity between 0.0 and 1.0."""
        words = task_text.split()
        length_score = min(len(words) / 900.0, 1.0)
        advanced_terms = {
            "architecture",
            "architect",
            "analyze",
            "multi-agent",
            "compliance",
            "migration",
            "platform",
            "reasoning",
            "optimize",
            "security",
            "distributed",
            "orchestration",
            "hallucination",
        }
        term_hits = sum(1 for word in words if word.lower().strip(".,:;()[]{}") in advanced_terms)
        term_score = min(term_hits / 5.0, 1.0)
        return round((length_score * 0.65) + (term_score * 0.35), 4)

    def route(self, task_text: str) -> RoutingDecision:
        """Return the selected model tier and model name."""
        complexity = self.estimate_complexity(task_text)
        if complexity >= self.complexity_threshold:
            return RoutingDecision(
                model_tier=ModelTier.LARGE,
                model_name=self.large_model_name,
                reason="complex_task",
                estimated_complexity=complexity,
            )
        return RoutingDecision(
            model_tier=ModelTier.SMALL,
            model_name=self.small_model_name,
            reason="simple_task",
            estimated_complexity=complexity,
        )

    def select_model(self, task_text: str, context: dict[str, object] | None = None) -> RoutingDecision:
        """Backward-compatible model-selection API."""
        combined_text = task_text
        if context:
            combined_text = f"{task_text}\n{context}"
        return self.route(combined_text)
