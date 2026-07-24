# File: tests/test_ats_engine.py
from __future__ import annotations

import asyncio

from src.agents.ats_engine import ATSEngine


def test_tfidf_score_returns_normalized_value() -> None:
    engine = ATSEngine()
    result = engine.score_with_tfidf("python fastapi sqlalchemy", "python backend fastapi")
    assert 0.0 <= result.score <= 1.0


def test_combined_score_returns_stubbed_weighted_score() -> None:
    engine = ATSEngine()
    result = asyncio.run(engine.combined_score("python", "python"))
    assert 0.0 <= result.score <= 1.0
