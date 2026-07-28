# File: src/clients/embeddings.py
"""Embedding infrastructure client supporting OpenAI text-embedding-3-small with sentence-transformers fallback."""

from __future__ import annotations

import math
import os
import re
from typing import Any, List

_SENTENCE_TRANSFORMER_MODEL: Any = None


def _get_openai_embedding(text: str, api_key: str) -> List[float] | None:
    """Fetch embedding using OpenAI API (text-embedding-3-small)."""
    try:
        import httpx

        response = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "text-embedding-3-small",
                "input": text,
            },
            timeout=10.0,
        )
        if response.status_code == 200:
            data = response.json()
            return data["data"][0]["embedding"]
    except Exception:
        pass
    return None


def _get_sentence_transformer_embedding(text: str) -> List[float] | None:
    """Fetch embedding using sentence-transformers/all-MiniLM-L6-v2."""
    global _SENTENCE_TRANSFORMER_MODEL
    try:
        if _SENTENCE_TRANSFORMER_MODEL is None:
            from sentence_transformers import SentenceTransformer
            _SENTENCE_TRANSFORMER_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        embedding = _SENTENCE_TRANSFORMER_MODEL.encode(text)
        return embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
    except Exception:
        pass
    return None


def _get_fallback_embedding(text: str, dim: int = 384) -> List[float]:
    """Generate a deterministic normalized frequency/hash fallback embedding vector."""
    tokens = re.findall(r"\b\w+\b", text.lower())
    vector = [0.0] * dim
    if not tokens:
        vector[0] = 1.0
        return vector

    for token in tokens:
        idx = abs(hash(token)) % dim
        vector[idx] += 1.0

    norm = math.sqrt(sum(x * x for x in vector))
    if norm > 0:
        vector = [x / norm for x in vector]
    return vector


def get_embedding(text: str) -> List[float]:
    """Get float embedding vector for given text.

    Tries OpenAI text-embedding-3-small (if OPENAI_API_KEY set).
    Falls back to sentence-transformers/all-MiniLM-L6-v2.
    Falls back to deterministic unit vector if both fail/unavailable.
    """
    if not text or not text.strip():
        return [0.0] * 384

    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        emb = _get_openai_embedding(text, api_key)
        if emb is not None:
            return emb

    st_emb = _get_sentence_transformer_embedding(text)
    if st_emb is not None:
        return st_emb

    return _get_fallback_embedding(text)
