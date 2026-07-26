from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

P = ParamSpec("P")
R = TypeVar("R")

# Network-only exceptions are retried. Authentication, validation, and other
# application errors must surface immediately instead of being retried blindly.
RETRIABLE_NETWORK_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.RemoteProtocolError)


def _is_retriable_network_error(exc: BaseException) -> bool:
    """Retry connection errors and provider rate-limit/transient server errors."""

    if isinstance(exc, RETRIABLE_NETWORK_ERRORS):
        return True
    status_code = getattr(getattr(exc, "resp", None), "status", None)
    if status_code is None:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
    return status_code == 429 or isinstance(status_code, int) and status_code >= 500


def retry_network(
    attempts: int = 3,
    min_wait_seconds: float = 0.5,
    max_wait_seconds: float = 10.0,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Apply bounded exponential-backoff retries to a sync network function."""

    return retry(
        retry=retry_if_exception(_is_retriable_network_error),
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=min_wait_seconds, min=min_wait_seconds, max=max_wait_seconds),
        reraise=True,
    )


def retry_async_network(
    attempts: int = 3,
    min_wait_seconds: float = 0.5,
    max_wait_seconds: float = 10.0,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Apply bounded exponential-backoff retries to an async network function."""

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        decorated = retry_network(attempts, min_wait_seconds, max_wait_seconds)(func)

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return await decorated(*args, **kwargs)  # type: ignore[misc]

        return wrapper

    return decorator


def retry_async_scrape(
    attempts: int = 3,
    min_wait_seconds: float = 1.0,
    max_wait_seconds: float = 10.0,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Backward-compatible alias for scraping, Tavily, and Gmail network calls."""

    return retry_async_network(attempts, min_wait_seconds, max_wait_seconds)


async def fetch_text_with_retry(fetcher: Callable[[str], Awaitable[str]], url: str) -> str:
    """Fetch text through an injected async fetcher with exponential backoff."""

    return await retry_async_scrape()(fetcher)(url)
