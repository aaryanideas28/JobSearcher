from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config.settings import get_settings


@dataclass(slots=True)
class OllamaGeneration:
    """Normalized result from a local Ollama generation request."""

    text: str
    model: str
    used_fallback: bool
    metadata: dict[str, Any]


class OllamaClient:
    """Async Ollama helper configured exclusively through application settings."""

    def __init__(self, base_url: str | None = None, timeout_seconds: float = 60.0) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _post_generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        # A local daemon should accept a connection promptly; retain the longer timeout
        # for generation while preventing offline callers from blocking a workflow.
        timeout = httpx.Timeout(self.timeout_seconds, connect=min(5.0, self.timeout_seconds))
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()
        return response.json()

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        options: dict[str, Any] | None = None,
        json_mode: bool = False,
    ) -> OllamaGeneration:
        """Generate text, returning structured failure metadata when Ollama is unavailable."""

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": options or {"temperature": 0.2},
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        try:
            data = await self._post_generate(payload)
        except httpx.HTTPError as exc:
            return OllamaGeneration("", model, True, {"provider": "ollama", "error": str(exc)})

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
