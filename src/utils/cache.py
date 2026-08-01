from __future__ import annotations

import time
import json
import logging
from typing import Any, Callable, Coroutine
from functools import wraps
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

# Fallback in-memory cache: dict mapping key -> (value, expire_time)
_IN_MEMORY_CACHE: dict[str, tuple[Any, float]] = {}

def get_redis_client() -> Any:
    """Lazy initialize redis client to handle connection failures gracefully."""
    try:
        import redis
        settings = get_settings()
        client = redis.from_url(
            settings.redis_url,
            socket_timeout=1.5,
            socket_connect_timeout=1.5,
            decode_responses=True
        )
        # Verify connection quickly
        client.ping()
        return client
    except Exception as e:
        logger.debug(f"Redis not available, using in-memory fallback: {e}")
        return None

def cache_jobs(ttl_seconds: int = 900) -> Callable:
    """Decorator to cache job discovery results using Redis or in-memory fallback."""
    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Coroutine[Any, Any, Any]]:
        @wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # discover signature: self, query, max_results=6, source="tavily", preferred_locations=None, work_mode=None
            query = kwargs.get("query") or (args[0] if len(args) > 0 else "")
            preferred_locations = kwargs.get("preferred_locations") or (args[3] if len(args) > 3 else [])
            work_mode = kwargs.get("work_mode") or (args[4] if len(args) > 4 else "Any")

            # Extract target_role from query for a clean cache key format: f"jobs:{target_role}:{preferred_locations}:{work_mode}"
            target_role = query.lower()
            if " jobs" in target_role:
                target_role = target_role.split(" jobs")[0].strip()
            else:
                target_role = target_role.strip()

            # Normalize locations
            if isinstance(preferred_locations, list):
                locs_str = ",".join(sorted([str(l).strip().lower() for l in preferred_locations]))
            else:
                locs_str = str(preferred_locations).strip().lower()

            cache_key = f"jobs:{target_role}:{locs_str}:{str(work_mode).strip().lower()}"

            # 1. Try to hit cache
            redis_client = get_redis_client()
            if redis_client:
                try:
                    cached_val = redis_client.get(cache_key)
                    if cached_val:
                        logger.info(f"Cache hit (Redis) for key: {cache_key}")
                        data = json.loads(cached_val)
                        from src.agents.job_discovery import JobPosting
                        return [JobPosting(**item) for item in data]
                except Exception as e:
                    logger.warning(f"Failed to read from Redis cache: {e}")
            else:
                if cache_key in _IN_MEMORY_CACHE:
                    val, expire_time = _IN_MEMORY_CACHE[cache_key]
                    if time.time() < expire_time:
                        logger.info(f"Cache hit (In-Memory) for key: {cache_key}")
                        return val

            # 2. Invoke actual search
            result = await func(self, *args, **kwargs)

            # 3. Store in cache
            if result:
                try:
                    serializable = []
                    for p in result:
                        serializable.append({
                            "title": p.title,
                            "company": p.company,
                            "location": p.location,
                            "url": p.url,
                            "description": p.description,
                            "metadata": p.metadata
                        })

                    if redis_client:
                        redis_client.setex(cache_key, ttl_seconds, json.dumps(serializable))
                    else:
                        _IN_MEMORY_CACHE[cache_key] = (result, time.time() + ttl_seconds)
                except Exception as e:
                    logger.warning(f"Failed to write to cache: {e}")

            return result
        return wrapper
    return decorator
