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

    def _augment_query(self, query: str, preferred_locations: list[str] | None = None, work_mode: str | None = None) -> str:
        query_terms = set(query.lower().split())
        extra_terms = []
        
        if work_mode and work_mode.lower() != "any":
            mode_term = "Remote" if "remote" in work_mode.lower() else work_mode
            if mode_term.lower() not in query_terms:
                extra_terms.append(mode_term)
                
        if preferred_locations:
            locs = [l.strip() for l in preferred_locations if l.strip()]
            if locs:
                locs_clean = []
                for l in locs:
                    if l.lower() not in query_terms and l.lower() not in [et.lower() for et in extra_terms]:
                        locs_clean.append(l)
                if locs_clean:
                    if len(locs_clean) == 1:
                        extra_terms.append(f"in {locs_clean[0]}")
                    else:
                        locs_str = " OR ".join(locs_clean)
                        extra_terms.append(f"in ({locs_str})")
                        
        if extra_terms:
            return f"{query} {' '.join(extra_terms)}"
        return query

    async def search_tavily(
        self,
        query: str,
        max_results: int = 5,
        preferred_locations: list[str] | None = None,
        work_mode: str | None = None,
    ) -> list[JobPosting]:
        """Search Tavily for job postings."""
        if not self.tavily_api_key:
            return []

        augmented_query = self._augment_query(query, preferred_locations, work_mode)

        payload: dict[str, Any] = {
            "api_key": self.tavily_api_key,
            "query": augmented_query,
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

    async def search_linkedin_tavily(
        self,
        query: str,
        max_results: int = 5,
        preferred_locations: list[str] | None = None,
        work_mode: str | None = None,
    ) -> list[JobPosting]:
        """Search Tavily specifically targeting LinkedIn job URLs."""
        if not self.tavily_api_key:
            return []
        targeted_query = f"site:linkedin.com/jobs/view {query}"
        return await self.search_tavily(
            query=targeted_query,
            max_results=max_results,
            preferred_locations=preferred_locations,
            work_mode=work_mode,
        )

    async def search_linkedin_local(
        self,
        query: str,
        max_results: int = 5,
        preferred_locations: list[str] | None = None,
        work_mode: str | None = None,
    ) -> list[JobPosting]:
        """Scrape LinkedIn jobs using linkedin-jobs-scraper library with try-except fallback."""
        try:
            import asyncio
            from linkedin_jobs_scraper import LinkedinScraper
            from linkedin_jobs_scraper.events import Events, EventData
            from linkedin_jobs_scraper.query import Query, QueryOptions, QueryFilters
            from linkedin_jobs_scraper.filters import RelevanceFilters
            import logging
            
            logging.getLogger('linkedin-jobs-scraper').setLevel(logging.WARNING)
            postings: list[JobPosting] = []

            def on_data(data: EventData):
                if len(postings) >= max_results:
                    return
                if any(p.url == data.link for p in postings):
                    return
                postings.append(
                    JobPosting(
                        title=data.title,
                        company=data.company,
                        location=data.location,
                        url=data.link,
                        description=data.description or "",
                        metadata={"source": "linkedin_local", "job_id": data.job_id}
                    )
                )

            def on_error(err):
                import sys
                print(f"LinkedIn local scraper error: {err}", file=sys.stderr)

            scraper = LinkedinScraper(
                chrome_executable_path=None,
                chrome_binary_location=None,
                headless=True,
                max_workers=1,
                slow_mo=2,
            )
            scraper.on(Events.DATA, on_data)
            scraper.on(Events.ERROR, on_error)

            location = "United States"
            clean_query = query
            if " in " in query.lower():
                parts = query.lower().split(" in ")
                clean_query = parts[0].strip()
                location = parts[1].strip().title()

            locations = [location]
            if preferred_locations:
                locations = [l.strip() for l in preferred_locations if l.strip()]

            # Incorporate work mode keyword into search query if set
            if work_mode and work_mode.lower() != "any":
                mode_kw = "Remote" if "remote" in work_mode.lower() else work_mode
                if mode_kw.lower() not in clean_query.lower():
                    clean_query = f"{clean_query} {mode_kw}"

            queries = [
                Query(
                    query=clean_query,
                    options=QueryOptions(
                        locations=locations,
                        apply_link=True,
                        limit=max_results,
                        filters=QueryFilters(
                            relevance=RelevanceFilters.RECENT
                        )
                    )
                )
            ]

            await asyncio.to_thread(scraper.run, queries)

            if not postings:
                import sys
                print("LinkedIn local scraper returned 0 results, falling back to Tavily", file=sys.stderr)
                return await self.search_linkedin_tavily(
                    query=query,
                    max_results=max_results,
                    preferred_locations=preferred_locations,
                    work_mode=work_mode,
                )

            return postings
        except Exception as exc:
            import sys
            print(f"Failed to run linkedin-jobs-scraper local: {exc}, falling back to Tavily", file=sys.stderr)
            return await self.search_linkedin_tavily(
                query=query,
                max_results=max_results,
                preferred_locations=preferred_locations,
                work_mode=work_mode,
            )

    async def discover(
        self,
        query: str,
        max_results: int = 5,
        source: str = "tavily",
        preferred_locations: list[str] | None = None,
        work_mode: str | None = None,
    ) -> list[JobPosting]:
        """Discover jobs using the configured provider and enrich details asynchronously."""
        if source == "linkedin_tavily":
            postings = await self.search_linkedin_tavily(
                query=query,
                max_results=max_results,
                preferred_locations=preferred_locations,
                work_mode=work_mode,
            )
        elif source == "linkedin_local":
            postings = await self.search_linkedin_local(
                query=query,
                max_results=max_results,
                preferred_locations=preferred_locations,
                work_mode=work_mode,
            )
        else:
            postings = await self.search_tavily(
                query=query,
                max_results=max_results,
                preferred_locations=preferred_locations,
                work_mode=work_mode,
            )

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

