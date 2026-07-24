# File: src/security/validation.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from pydantic import BaseModel, ValidationError, create_model
except ImportError:  # pragma: no cover - dependency bootstrap fallback
    BaseModel = object  # type: ignore[assignment]
    ValidationError = ValueError  # type: ignore[assignment]
    create_model = None  # type: ignore[assignment]


@dataclass(slots=True)
class ValidationResult:
    """Generic validation result with structured reasons."""

    valid: bool
    reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class PromptInjectionGuard:
    """Detect obvious prompt injection attempts in untrusted content."""

    blocked_phrases: tuple[str, ...] = (
        "ignore previous instructions",
        "system prompt",
        "developer message",
        "reveal your instructions",
    )

    def inspect(self, text: str) -> ValidationResult:
        """Inspect text for prompt injection markers."""

        lowered = text.lower()
        matches = [phrase for phrase in self.blocked_phrases if phrase in lowered]
        return ValidationResult(valid=not matches, reasons=matches)


class JSONSchemaValidator:
    """Validate dictionaries against a lightweight expected-key schema."""

    def validate(self, payload: dict[str, Any], required_keys: set[str] | None = None) -> ValidationResult:
        """Validate required keys exist in a payload."""

        missing = sorted((required_keys or set()) - set(payload))
        return ValidationResult(valid=not missing, reasons=[f"missing:{key}" for key in missing])


class HallucinationDetector:
    """Detect generated claims that are unsupported by source resume facts."""

    def detect(self, generated_text: str, source_facts: list[str]) -> ValidationResult:
        """Return a placeholder hallucination assessment."""

        _ = generated_text
        return ValidationResult(valid=True, reasons=[], metadata={"source_fact_count": len(source_facts)})
