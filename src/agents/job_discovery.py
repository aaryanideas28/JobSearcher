# File: src/agents/job_discovery.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config.settings import get_settings

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
        self.tavily_api_key = tavily_api_key or get_settings().tavily_api_key
        self.timeout_seconds = timeout_seconds

    async def search_tavily(self, query: str, max_results: int = 10) -> list[JobPosting]:
        """Search Tavily for job postings."""

        if httpx is None or not self.tavily_api_key:
            return []

        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": True,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post("https://api.tavily.com/search", json=payload)
            response.raise_for_status()

        data = response.json()
        postings: list[JobPosting] = []
        for result in data.get("results", []):
            title = str(result.get("title") or "Discovered role")
            url = str(result.get("url") or "")
            content = str(result.get("raw_content") or result.get("content") or "")
            postings.append(
                JobPosting(
                    title=title,
                    company=self._infer_company(title=title, url=url),
                    url=url,
                    description=content,
                    metadata={"source": "tavily", "score": result.get("score")},
                )
            )
        return postings

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

    def _infer_company(self, title: str, url: str) -> str:
        """Infer a company label from a title or URL when providers omit it."""

        if " at " in title:
            return title.rsplit(" at ", maxsplit=1)[-1].strip()
        if " - " in title:
            return title.rsplit(" - ", maxsplit=1)[-1].strip()
        host = url.split("//")[-1].split("/")[0].replace("www.", "")
        return host or "Unknown Company"
