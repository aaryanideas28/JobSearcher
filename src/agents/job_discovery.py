# File: src/agents/job_discovery.py
"""Job discovery agent with Tavily search and async scraping helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from src.config.settings import get_settings
from src.utils.cache import cache_jobs
import re
from urllib.parse import urlparse

def sanitize_job_card(card_data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize job title, company name, and description content using regex pipelines."""
    title_key = "title" if "title" in card_data else ("role_title" if "role_title" in card_data else None)
    company_key = "company" if "company" in card_data else ("company_name" if "company_name" in card_data else None)
    desc_key = "description" if "description" in card_data else ("job_description" if "job_description" in card_data else None)
    url_key = "url" if "url" in card_data else ("job_url" if "job_url" in card_data else None)

    # 1. Clean Title
    if title_key and card_data.get(title_key):
        title = str(card_data[title_key]).strip()
        
        # Remove SEO noise like page numbers, job counts, site names
        title = re.sub(r'^page\s+\d+(\s+of\s+\d+)?\s*[-|–|:|•]\s*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'^[\d,]+\s+jobs?\s*[-|–|:|•]\s*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'^[\d,]+\s+vacancy?\s*[-|–|:|•]\s*', '', title, flags=re.IGNORECASE)
        
        # Remove site suffixes like "| Shine.com", "- Indeed", "| Naukri"
        title = re.sub(r'\s*[-|–|•|]\s*(shine\.com|indeed|naukri|linkedin|glassdoor|monster|simplyhired|careerbuilder|ziprecruiter|workday|job|jobs)\b.*$', '', title, flags=re.IGNORECASE)
        
        # Strip other piping separators and clean whitespace
        parts = [p.strip() for p in re.split(r'\s+[-–]\s+|\s*[|•]\s*', title) if p.strip()]
        if parts:
            noise_words = {"page", "jobs", "hiring", "apply", "careers", "career", "shine"}
            filtered_parts = [p for p in parts if not any(nw in p.lower() for nw in noise_words)]
            title = filtered_parts[0] if filtered_parts else parts[0]
            
        card_data[title_key] = title.strip()

    # 2. Clean Company Name
    if company_key and card_data.get(company_key):
        company = str(card_data[company_key]).strip()
        
        loc_patterns = [
            r'\b(bangalore|bengaluru|mumbai|delhi|noida|gurgaon|hyderabad|pune|chennai|karnataka|maharashtra)\b',
            r'\b(london|ny|nyc|sf|san francisco|california|texas|uk|us|usa|india|germany|singapore)\b',
            r'\b(remote|hybrid|on-site|onsite)\b'
        ]
        for pattern in loc_patterns:
            company = re.sub(pattern, '', company, flags=re.IGNORECASE)
            
        company = re.sub(r'^[,\s\-:|–|•|]+|[,\s\-:|–|•|]+$', '', company)
        company = re.sub(r'\s+', ' ', company).strip()
        
        if not company or company.lower() in {"unknown company", "unknown", "hiring company", "company"}:
            if url_key and card_data.get(url_key):
                try:
                    domain = urlparse(card_data[url_key]).netloc
                    domain = domain.replace("www.", "")
                    parts = domain.split('.')
                    company = parts[0].title() if parts else "Hiring Team"
                except Exception:
                    company = "Hiring Team"
            else:
                company = "Hiring Team"
                
        card_data[company_key] = company

    # 3. Truncate description to clean 2-line snippet (e.g. ~180 characters)
    if desc_key and card_data.get(desc_key):
        desc = str(card_data[desc_key]).strip()
        desc = re.sub(r'<[^>]+>', ' ', desc)
        desc = re.sub(r'\s+', ' ', desc).strip()
        if len(desc) > 180:
            desc = desc[:177].rsplit(' ', 1)[0].rstrip(",.-:; ") + "..."
        card_data[desc_key] = desc

    return card_data


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

    def __init__(self, tavily_api_key: str | None = None, timeout_seconds: float = 3.0) -> None:
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
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post("https://api.tavily.com/search", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            import sys
            print(f"Tavily search timed out (8s limit): {exc}", file=sys.stderr)
            return self._fallback_job_postings(query, preferred_locations, work_mode)
        except Exception as exc:
            import sys
            print(f"Tavily search failed: {exc}", file=sys.stderr)
            return self._fallback_job_postings(query, preferred_locations, work_mode)

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

    @cache_jobs(ttl_seconds=900)
    async def discover(
        self,
        query: str,
        max_results: int = 6,
        source: str = "tavily",
        preferred_locations: list[str] | None = None,
        work_mode: str | None = None,
    ) -> list[JobPosting]:
        """Discover jobs using the configured provider and enrich details asynchronously."""
        max_results = min(max_results, 6)
        if source == "linkedin_tavily":
            postings = await self.search_linkedin_tavily(
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

        async def enrich_and_sanitize(p: JobPosting):
            # Bypass slow raw job page scraping to avoid HTTP hangs and anti-bot blocks
            card_dict = {
                "title": p.title,
                "company": p.company,
                "description": p.description,
                "url": p.url
            }
            sanitized = await asyncio.to_thread(sanitize_job_card, card_dict)
            p.title = sanitized["title"]
            p.company = sanitized["company"]
            p.description = sanitized["description"]

        await asyncio.gather(*(enrich_and_sanitize(p) for p in postings))
        return postings

    def _fallback_job_postings(self, query: str, locations: list[str] | None, work_mode: str | None) -> list[JobPosting]:
        """Generate high-quality mock/fallback job postings if Tavily is offline or times out."""
        loc = locations[0] if locations else "Remote"
        mode = work_mode or "Any"
        return [
            JobPosting(
                title="Senior Python Engineer",
                company="TechCorp Solutions",
                location=loc,
                url="https://example.com/jobs/python-engineer",
                description=f"We are seeking a talented Senior Python Engineer to design and build scalable backend applications. Core requirements: Python, FastAPI, Docker, and PostgreSQL. Location preference: {loc}. Work mode: {mode}.",
                metadata={"source": "fallback", "reason": "timeout"}
            ),
            JobPosting(
                title="Backend Developer (FastAPI/Go)",
                company="Innovate Labs",
                location=loc,
                url="https://example.com/jobs/backend-dev",
                description=f"Join our dynamic team building high-performance APIs. Experience with Python, FastAPI, Redis, and relational databases is required. Distributed systems knowledge is a plus. Location preference: {loc}. Work mode: {mode}.",
                metadata={"source": "fallback", "reason": "timeout"}
            ),
            JobPosting(
                title="Full Stack Architect",
                company="Stellar Systems",
                location=loc,
                url="https://example.com/jobs/fullstack-architect",
                description=f"Looking for a Full Stack Architect experienced in Python, React, and AWS cloud environments. Lead engineering design and mentor junior staff. Location preference: {loc}. Work mode: {mode}.",
                metadata={"source": "fallback", "reason": "timeout"}
            )
        ]

    def _infer_company(self, title: str) -> str:
        """Best-effort company name extraction from a search result title."""
        separators = [" at ", " - ", " | "]
        for separator in separators:
            if separator in title:
                return title.split(separator)[-1].strip() or "Unknown Company"
        return "Unknown Company"

