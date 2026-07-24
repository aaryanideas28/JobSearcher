# File: src/agents/job_discovery.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover - dependency bootstrap fallback
    httpx = None  # type: ignore[assignment]


@dataclass(slots=True)
class JobPosting:
    """Normalized job posting returned by discovery providers."""

    title: str
    company: str
    url: str
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class JobDiscoveryAgent:
    """Agent for discovering jobs from Tavily and async scraping sources."""

    def __init__(self, tavily_api_key: str | None = None, timeout_seconds: float = 15.0) -> None:
        self.tavily_api_key = tavily_api_key
        self.timeout_seconds = timeout_seconds

    async def search_tavily(self, query: str, max_results: int = 10) -> list[JobPosting]:
        """Search Tavily for job postings."""

        _ = (query, max_results)
        return []

    async def scrape_job_page(self, url: str) -> JobPosting:
        """Scrape a job page into a normalized posting."""

        if httpx is None:
            return JobPosting(title="", company="", url=url, metadata={"reason": "httpx_unavailable"})
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(url)
            response.raise_for_status()
        return JobPosting(title="", company="", url=url, description=response.text, metadata={"source": "scrape"})

    async def discover(self, query: str, max_results: int = 10) -> list[JobPosting]:
        """Run the configured discovery strategy."""

        return await self.search_tavily(query=query, max_results=max_results)
