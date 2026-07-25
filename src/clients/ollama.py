# File: src/clients/ollama.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from config.settings import get_settings


@dataclass(slots=True)
class OllamaGeneration:
    """Normalized response from an Ollama generation call."""

    text: str
    model: str
    used_fallback: bool
    metadata: dict[str, Any]


class OllamaClient:
    """Small async client for local Ollama text generation."""

    def __init__(self, base_url: str | None = None, timeout_seconds: float = 60.0) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> OllamaGeneration:
        """Generate text with Ollama, returning a deterministic fallback if Ollama is offline."""

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": options or {"temperature": 0.2},
        }
        if system:
            payload["system"] = system

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            return OllamaGeneration(
                text=self._fallback_text(prompt),
                model=model,
                used_fallback=True,
                metadata={"error": str(exc), "provider": "ollama"},
            )

        data = response.json()
        return OllamaGeneration(
            text=str(data.get("response", "")).strip(),
            model=str(data.get("model", model)),
            used_fallback=False,
            metadata={
                "provider": "ollama",
                "total_duration": data.get("total_duration"),
                "eval_count": data.get("eval_count"),
            },
        )

    async def status(self) -> dict[str, Any]:
        """Return local Ollama availability and installed model metadata."""

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
        except httpx.HTTPError as exc:
            return {"available": False, "base_url": self.base_url, "error": str(exc), "models": []}

        data = response.json()
        models = [
            {
                "name": item.get("name"),
                "modified_at": item.get("modified_at"),
                "size": item.get("size"),
            }
            for item in data.get("models", [])
        ]
        return {"available": True, "base_url": self.base_url, "models": models}

    def _fallback_text(self, prompt: str) -> str:
        """Return useful local text when Ollama is unavailable."""

        excerpt = prompt.strip().splitlines()
        compact = " ".join(line.strip() for line in excerpt if line.strip())
        return compact[:3000]
