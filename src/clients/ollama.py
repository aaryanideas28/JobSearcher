from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config.settings import get_settings


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

    async def query_local_llm(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        options: dict[str, Any] | None = None,
        json_mode: bool = False,
    ) -> OllamaGeneration:
        """Query Hugging Face serverless Inference API directly, bypassing Ollama completely."""
        settings = get_settings()
        api_key = settings.huggingface_api_key

        if not api_key:
            return OllamaGeneration(
                text="{}",
                model=model,
                used_fallback=True,
                metadata={"provider": "none", "error": "huggingface_api_key_missing"},
            )

        hf_model = "Qwen/Qwen2.5-7B-Instruct"
        if "3b" in model.lower() or "1b" in model.lower() or "small" in model.lower():
            hf_model = "Qwen/Qwen2.5-3B-Instruct"

        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            system_prompt = system or "You are a helpful assistant."
            inputs = f"<|system|>\n{system_prompt}\n<|user|>\n{prompt}\n<|assistant|>\n"

            hf_payload = {
                "inputs": inputs,
                "parameters": {
                    "temperature": 0.2,
                    "max_new_tokens": 1024,
                },
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"https://api-inference.huggingface.co/models/{hf_model}",
                    json=hf_payload,
                    headers=headers,
                )
                response.raise_for_status()
                res_data = response.json()

                text = ""
                if isinstance(res_data, list) and len(res_data) > 0:
                    text = res_data[0].get("generated_text", "")
                elif isinstance(res_data, dict):
                    text = res_data.get("generated_text", "")

                if text:
                    if text.startswith(inputs):
                        text = text[len(inputs):].strip()
                    return OllamaGeneration(
                        text=text.strip(),
                        model=hf_model,
                        used_fallback=False,
                        metadata={"provider": "huggingface", "model": hf_model},
                    )
        except Exception as exc:
            # Fallback to OpenAI if configured
            if settings.openai_api_key:
                try:
                    headers = {
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json",
                    }
                    openai_payload = {
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": system or "You are a helpful assistant."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.2,
                    }
                    if json_mode:
                        openai_payload["response_format"] = {"type": "json_object"}

                    async with httpx.AsyncClient(timeout=15.0) as client:
                        response = await client.post("https://api.openai.com/v1/chat/completions", json=openai_payload, headers=headers)
                        response.raise_for_status()
                        res_json = response.json()
                        text = res_json["choices"][0]["message"]["content"].strip()
                        return OllamaGeneration(
                            text=text,
                            model="gpt-4o-mini",
                            used_fallback=True,
                            metadata={"provider": "openai_fallback", "original_model": model},
                        )
                except Exception:
                    pass

        return OllamaGeneration(
            text="{}",
            model=model,
            used_fallback=True,
            metadata={"provider": "none", "error": "generation_failed"},
        )

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        options: dict[str, Any] | None = None,
        json_mode: bool = False,
    ) -> OllamaGeneration:
        """Backward-compatible generation entry point calling query_local_llm."""
        return await self.query_local_llm(
            model=model,
            prompt=prompt,
            system=system,
            options=options,
            json_mode=json_mode,
        )
