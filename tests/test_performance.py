# File: tests/test_performance.py
from __future__ import annotations

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.job_discovery import JobDiscoveryAgent, JobPosting
from src.utils.cache import cache_jobs, _IN_MEMORY_CACHE


@pytest.mark.anyio
async def test_cache_jobs_decorator_in_memory() -> None:
    # Clear in-memory cache
    _IN_MEMORY_CACHE.clear()

    call_count = 0

    class DummyAgent:
        @cache_jobs(ttl_seconds=10)
        async def discover(
            self,
            query: str,
            max_results: int = 5,
            source: str = "tavily",
            preferred_locations: list[str] | None = None,
            work_mode: str | None = None
        ) -> list[JobPosting]:
            nonlocal call_count
            call_count += 1
            return [
                JobPosting(
                    title="Mock Engineer",
                    company="MockCorp",
                    location="Remote",
                    url="https://mock.com",
                    description="Details"
                )
            ]

    agent = DummyAgent()
    
    with patch("src.utils.cache.get_redis_client", return_value=None):
        # First call (should execute method)
        res1 = await agent.discover(query="Python jobs", preferred_locations=["Remote"], work_mode="Remote")
        assert call_count == 1
        assert len(res1) == 1
        assert res1[0].company == "MockCorp"

        # Second call (should hit cache)
        res2 = await agent.discover(query="Python jobs", preferred_locations=["Remote"], work_mode="Remote")
        assert call_count == 1
        assert len(res2) == 1
        assert res2[0].company == "MockCorp"

        # Different parameters (should execute method again)
        res3 = await agent.discover(query="Go jobs", preferred_locations=["Remote"], work_mode="Remote")
        assert call_count == 2
        assert len(res3) == 1


def test_tavily_search_fallback_trigger() -> None:
    agent = JobDiscoveryAgent(tavily_api_key="mock_key")
    fallbacks = agent._fallback_job_postings(
        query="Frontend developer jobs",
        locations=["Mumbai"],
        work_mode="Hybrid"
    )

    assert len(fallbacks) == 3
    assert fallbacks[0].location == "Mumbai"
    assert "Mumbai" in fallbacks[0].description
    assert "Hybrid" in fallbacks[0].description
