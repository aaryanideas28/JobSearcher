# File: src/security/validation.py
from __future__ import annotations

import re
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
        "delete all files",
        "exfiltrate",
        "bypass validation",
    )

    def inspect(self, text: str) -> ValidationResult:
        """Inspect text for prompt injection markers."""

        lowered = text.lower()
        matches = [phrase for phrase in self.blocked_phrases if phrase in lowered]
        suspicious_url = bool(re.search(r"https?://\S+", text)) and "prompt" in lowered
        reasons = matches + (["suspicious_prompt_url"] if suspicious_url else [])
        return ValidationResult(valid=not reasons, reasons=reasons)


class JSONSchemaValidator:
    """Validate dictionaries against a small JSON-schema subset."""

    type_map: dict[str, type[Any] | tuple[type[Any], ...]] = {
        "array": list,
        "boolean": bool,
        "integer": int,
        "number": (int, float),
        "object": dict,
        "string": str,
    }

    def validate(self, payload: dict[str, Any], schema: dict[str, Any] | None = None) -> ValidationResult:
        """Validate required keys and primitive property types."""

        schema = schema or {}
        reasons: list[str] = []
        required = set(schema.get("required", []))
        reasons.extend(f"missing:{key}" for key in sorted(required - set(payload)))

        properties: dict[str, dict[str, Any]] = schema.get("properties", {})
        for key, rules in properties.items():
            if key not in payload or "type" not in rules:
                continue
            expected = self.type_map.get(str(rules["type"]))
            if expected is not None and not isinstance(payload[key], expected):
                reasons.append(f"type:{key}:expected_{rules['type']}")

        return ValidationResult(valid=not reasons, reasons=reasons)


class HallucinationDetector:
    """Detect generated claims that are unsupported by source resume facts."""

    ignored_terms: set[str] = {
        "Application",
        "Candidate",
        "Company",
        "Dear",
        "Draft",
        "Hiring",
        "Resume",
        "Summary",
        "Target",
        "Targeted",
        "Team",
        "Thank",
        "Thanks",
    }

    def detect(
        self,
        generated_text: str,
        source_facts: list[str],
        allowed_terms: list[str] | None = None,
    ) -> ValidationResult:
        """Flag generated named entities that are not present in known source facts."""

        allowlist = {term.lower() for term in (allowed_terms or []) if term}
        source_blob = " ".join(source_facts).lower()
        generated_entities = set(re.findall(r"\b[A-Z][A-Za-z0-9.+#-]{2,}\b", generated_text))
        unsupported = sorted(
            entity
            for entity in generated_entities
            if entity not in self.ignored_terms
            and entity.lower() not in source_blob
            and entity.lower() not in allowlist
        )
        return ValidationResult(
            valid=not unsupported,
            reasons=[f"unsupported_claim:{entity}" for entity in unsupported],
            metadata={
                "source_fact_count": len(source_facts),
                "unsupported_count": len(unsupported),
                "allowed_terms_count": len(allowlist),
            },
        )
