from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

<<<<<<< HEAD
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config.settings import get_settings
from src.workflow.state import AgentState
=======
from config.settings import get_settings

try:
    import httpx
except ImportError:  # pragma: no cover - dependency bootstrap fallback
    httpx = None  # type: ignore[assignment]
>>>>>>> bac5900d7d9b4ef2c0b5607ef1cf12e192b4817a


@dataclass(slots=True)
class JobPosting:
    """Normalized job posting returned by job discovery providers."""

    title: str
    company: str
    url: str
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class _VisibleTextParser(HTMLParser):
    """Extract visible text without adding a scraping dependency."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data.strip():
            self.parts.append(data.strip())


class JobDiscoveryAgent:
    """Find and scrape job postings through Tavily using async, retried I/O."""

    def __init__(self, tavily_api_key: str | None = None, timeout_seconds: float = 15.0) -> None:
        self.tavily_api_key = tavily_api_key or get_settings().tavily_api_key
        self.timeout_seconds = timeout_seconds

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _tavily_request(self, query: str, max_results: int) -> dict[str, Any]:
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
        return response.json()

<<<<<<< HEAD
    async def search_tavily(self, query: str, max_results: int = 10) -> list[JobPosting]:
        """Search Tavily and normalize its results. Missing configuration is non-fatal."""

        if not self.tavily_api_key:
            return []
        data = await self._tavily_request(query, max(1, min(max_results, 20)))
        return [
            JobPosting(
                title=str(result.get("title") or "Discovered role"),
                company=self._infer_company(str(result.get("title") or ""), str(result.get("url") or "")),
                url=str(result.get("url") or ""),
                description=str(result.get("raw_content") or result.get("content") or ""),
                metadata={"source": "tavily", "score": result.get("score")},
            )
            for result in data.get("results", [])
            if result.get("url")
        ]

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _fetch_page(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "KaizenJobDiscovery/1.0"})
            response.raise_for_status()
        return response.text
=======
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
>>>>>>> bac5900d7d9b4ef2c0b5607ef1cf12e192b4817a

    async def scrape_job_page(self, url: str) -> JobPosting:
        """Fetch a page and extract readable job text with retry protection."""

        html = await self._fetch_page(url)
        parser = _VisibleTextParser()
        parser.feed(html)
        return JobPosting(
            title="",
            company=self._infer_company("", url),
            url=url,
            description=" ".join(parser.parts),
            metadata={"source": "scrape"},
        )

    async def discover(self, query: str, max_results: int = 10) -> list[JobPosting]:
        """Search and concurrently enrich results that lack Tavily page content."""

<<<<<<< HEAD
        postings = await self.search_tavily(query, max_results)
        missing = [posting for posting in postings if not posting.description.strip()]
        pages = await asyncio.gather(*(self.scrape_job_page(posting.url) for posting in missing), return_exceptions=True)
        for posting, page in zip(missing, pages, strict=True):
            if isinstance(page, JobPosting):
                posting.description = page.description
                posting.metadata["scraped"] = True
            elif isinstance(page, Exception):
                posting.metadata["scrape_error"] = str(page)
        return postings

    async def run(self, state: AgentState, max_results: int = 10) -> AgentState:
        """Populate ``discovered_jobs`` on the shared agent state."""

        query = " ".join(part for part in (state.target_role, state.target_company) if part) or str(state.metadata.get("job_query", ""))
        if not query:
            state.validation_errors.append("A target_role, target_company, or metadata.job_query is required for discovery.")
            return state
        postings = await self.discover(query, max_results)
        state.discovered_jobs = [
            {"title": item.title, "company": item.company, "url": item.url, "description": item.description, "metadata": item.metadata}
            for item in postings
        ]
        state.workflow_status = "jobs_discovered"
        return state

    @staticmethod
    def _infer_company(title: str, url: str) -> str:
        if " at " in title.lower():
            return title.rsplit(" at ", 1)[-1].strip()
        if " - " in title:
            return title.rsplit(" - ", 1)[-1].strip()
        return urlparse(url).netloc.removeprefix("www.") or "Unknown Company"
=======
        return await self.search_tavily(query=query, max_results=max_results)

    def _infer_company(self, title: str, url: str) -> str:
        """Infer a company label from a title or URL when providers omit it."""

        if " at " in title:
            return title.rsplit(" at ", maxsplit=1)[-1].strip()
        if " - " in title:
            return title.rsplit(" - ", maxsplit=1)[-1].strip()
        host = url.split("//")[-1].split("/")[0].replace("www.", "")
        return host or "Unknown Company"
>>>>>>> bac5900d7d9b4ef2c0b5607ef1cf12e192b4817a
