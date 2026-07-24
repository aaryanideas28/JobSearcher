# File: src/utils/scraper_utils.py
from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

try:
    from tenacity import retry, stop_after_attempt, wait_exponential
except ImportError:  # pragma: no cover - dependency bootstrap fallback
    retry = None  # type: ignore[assignment]
    stop_after_attempt = None  # type: ignore[assignment]
    wait_exponential = None  # type: ignore[assignment]

P = ParamSpec("P")
R = TypeVar("R")


def retry_async_scrape(
    attempts: int = 3,
    min_wait_seconds: float = 1.0,
    max_wait_seconds: float = 10.0,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Return a retry decorator for async scraping functions."""

    if retry is None or stop_after_attempt is None or wait_exponential is None:
        def identity_decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
            @wraps(func)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                return await func(*args, **kwargs)

            return wrapper

        return identity_decorator

    return retry(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(min=min_wait_seconds, max=max_wait_seconds),
        reraise=True,
    )


async def fetch_text_with_retry(fetcher: Callable[[str], Awaitable[str]], url: str) -> str:
    """Fetch text through an injected async fetcher."""

    decorated_fetcher = retry_async_scrape()(fetcher)
    return await decorated_fetcher(url)
