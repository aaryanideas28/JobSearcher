# File: src/agents/job_discovery.py
"""Job discovery agent with Tavily search and async scraping helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from src.config.settings import get_settings


@dataclass(slots=True)
class JobPosting:
    """Normalized job posting returned by discovery providers."""

    title: str
    company: str
    location: str | None
    url: str
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)


class JobDiscoveryAgent:
    """Discover jobs through Tavily search and optional async page scraping."""

    def __init__(self, tavily_api_key: str | None = None, timeout_seconds: float = 15.0) -> None:
        settings = get_settings()
        self.tavily_api_key = tavily_api_key or settings.tavily_api_key
        self.timeout_seconds = timeout_seconds

    async def search_tavily(self, query: str, max_results: int = 5) -> list[JobPosting]:
        """Search Tavily for job postings."""
        if not self.tavily_api_key:
            return []

        payload: dict[str, Any] = {
            "api_key": self.tavily_api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": True,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post("https://api.tavily.com/search", json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            import sys
            print(f"Tavily search failed: {exc}", file=sys.stderr)
            return []

        postings: list[JobPosting] = []
        for item in data.get("results", []):
            title = str(item.get("title") or "Untitled Role")
            url = str(item.get("url") or "")
            description = str(item.get("content") or item.get("raw_content") or "")
            postings.append(
                JobPosting(
                    title=title,
                    company=self._infer_company(title),
                    location=None,
                    url=url,
                    description=description,
                    metadata={"source": "tavily", "score": item.get("score")},
                )
            )
        return postings

    async def scrape_job_page(self, url: str) -> str:
        """Fetch raw page text for a job URL."""
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    async def discover(self, query: str, max_results: int = 5) -> list[JobPosting]:
        """Discover jobs using the configured provider and enrich details asynchronously."""
        postings = await self.search_tavily(query=query, max_results=max_results)

        import asyncio
        import re

        async def enrich(posting: JobPosting):
            if posting.url and len(posting.description) < 250:
                try:
                    text = await self.scrape_job_page(posting.url)
                    if text:
                        clean_text = re.sub(r'<[^>]+>', ' ', text)
                        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                        if len(clean_text) > len(posting.description):
                            posting.description = clean_text[:2000]
                except Exception:
                    pass

        await asyncio.gather(*(enrich(p) for p in postings))
        return postings

    def _infer_company(self, title: str) -> str:
        """Best-effort company name extraction from a search result title."""
        separators = [" at ", " - ", " | "]
        for separator in separators:
            if separator in title:
                return title.split(separator)[-1].strip() or "Unknown Company"
        return "Unknown Company"
