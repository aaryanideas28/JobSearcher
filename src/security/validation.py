from __future__ import annotations

import re
import re
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.workflow.state import AgentState

ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass(slots=True)
class ValidationResult:
    """Validation result deliberately safe to return to a caller or workflow."""

    valid: bool
    reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class SafeLLMContact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: list[str] = Field(default_factory=list)


class SafeLLMResume(BaseModel):
    """Strict, crash-resistant schema accepted from a resume-producing LLM."""

    model_config = ConfigDict(extra="forbid", strict=True)
    contact: SafeLLMContact = Field(default_factory=SafeLLMContact)
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[dict[str, Any]] = Field(default_factory=list)
    education: list[dict[str, Any]] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)


class PromptInjectionGuard:
    """Fast, deterministic screening for hostile instructions in untrusted text."""

    _patterns: tuple[tuple[str, str], ...] = (
        ("ignore_instructions", r"\b(ignore|disregard|override)\s+(all\s+)?(previous|prior|system|developer)\s+(instructions?|rules?)"),
        ("prompt_exfiltration", r"\b(reveal|show|print|dump|repeat)\s+(the\s+)?(system\s+prompt|developer\s+message|instructions?)"),
        ("role_override", r"\b(act as|you are now|switch to)\s+(system|developer|jailbreak)\b"),
        ("role_tag", r"<\s*/?\s*(system|developer|assistant)\s*>"),
    )

    def inspect(self, text: str) -> ValidationResult:
        if not isinstance(text, str):
            return ValidationResult(False, ["invalid_text_type"])
        matches = [name for name, pattern in self._patterns if re.search(pattern, text, re.IGNORECASE)]
        return ValidationResult(not matches, matches, {"length": len(text)})


class JSONSchemaValidator:
    """Validate untrusted JSON/LLM output before downstream code accesses it."""

    def validate(self, payload: object, required_keys: set[str] | None = None) -> ValidationResult:
        if not isinstance(payload, dict):
            return ValidationResult(False, ["payload_must_be_object"])
        missing = sorted((required_keys or set()) - set(payload))
        return ValidationResult(not missing, [f"missing:{key}" for key in missing])

    def parse_model(self, payload: object, schema: type[ModelT]) -> tuple[ModelT | None, ValidationResult]:
        """Safely parse a Pydantic model without allowing malformed output to crash a workflow."""

        try:
            return schema.model_validate(payload), ValidationResult(True)
        except ValidationError as exc:
            errors = [f"{'.'.join(str(part) for part in error['loc'])}:{error['msg']}" for error in exc.errors()]
            return None, ValidationResult(False, errors)

    def parse_resume(self, payload: object) -> tuple[SafeLLMResume | None, ValidationResult]:
        return self.parse_model(payload, SafeLLMResume)


class HallucinationDetector:
    """Flag unsupported concrete claims in a generated cover letter."""

    _claim_sentence = re.compile(r"(?<=[.!?])\s+|\n+")
    _number = re.compile(r"\b\d+(?:\.\d+)?(?:%|\+)?\b")
    _proper_noun = re.compile(r"\b[A-Z][A-Za-z0-9&.-]{2,}\b")
    _ignored_entities = frozenset({"Dear", "Hello", "Hiring", "Team", "Thank", "Regards", "Sincerely", "I", "My", "The", "Your"})

    def detect(self, generated_text: str, source_facts: list[str], allowed_terms: list[str] | None = None) -> ValidationResult:
        if not isinstance(generated_text, str) or not all(isinstance(item, str) for item in source_facts):
            return ValidationResult(False, ["invalid_hallucination_input"])
        source = " ".join(source_facts + (allowed_terms or [])).lower()
        unsupported: list[str] = []
        for sentence in self._claim_sentence.split(generated_text):
            if not sentence.strip():
                continue
            for number in self._number.findall(sentence):
                if number.lower() not in source:
                    unsupported.append(f"unsupported_number:{number}")
            for entity in self._proper_noun.findall(sentence):
                if entity in self._ignored_entities:
                    continue
                if entity.lower() not in source:
                    unsupported.append(f"unsupported_entity:{entity}")
        return ValidationResult(not unsupported, sorted(set(unsupported)), {"source_fact_count": len(source_facts)})

    def detect_cover_letter(self, state: AgentState) -> ValidationResult:
        """Validate cover-letter claims against resume/job facts already in AgentState."""

        facts = [state.resume_text, state.job_description, state.optimized_resume]
        facts.extend(self._flatten(state.user_resume_json))
        facts.extend(self._flatten(state.extracted_facts))
        allowed = [value for value in (state.target_company, state.target_role) if value]
        return self.detect(state.cover_letter, facts, allowed)

    @staticmethod
    def _flatten(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [item for nested in value.values() for item in HallucinationDetector._flatten(nested)]
        if isinstance(value, list):
            return [item for nested in value for item in HallucinationDetector._flatten(nested)]
        return []
