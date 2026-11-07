"""DataMind v2 Sliding-Window Rate Limiter.

Uses Redis for distributed sliding-window rate limiting with an in-memory
fallback if Redis is unreachable. Returns standard Retry-After metadata.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("datamind.security.rate_limiter")


class RateLimiter:
    """Sliding-window rate limiter with Redis backend and in-memory fallback."""

    _redis_client: aioredis.Redis | None = None
    _in_memory_buckets: dict[str, list[float]] = {}

    @classmethod
    async def get_redis(cls) -> aioredis.Redis | None:
        """Lazily initialize and return Redis client."""
        if cls._redis_client is None:
            try:
                cls._redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                )
                await cls._redis_client.ping()
            except Exception as e:
                logger.warning(
                    f"Redis unavailable for rate limiting ({e}); falling back to in-memory."
                )
                cls._redis_client = None
        return cls._redis_client

    @classmethod
    async def check(cls, key: str, max_requests: int, window_seconds: int) -> dict[str, Any]:
        """Perform sliding window check."""
        now = time.time()
        client = await cls.get_redis()

        if client:
            try:
                redis_key = f"ratelimit:{key}"
                pipe = client.pipeline()
                # Remove timestamps older than window
                pipe.zremrangebyscore(redis_key, 0, now - window_seconds)
                # Count remaining items in window
                pipe.zcard(redis_key)
                # Add current timestamp
                pipe.zadd(redis_key, {str(now): now})
                # Set TTL on set
                pipe.expire(redis_key, window_seconds + 5)
                results = await pipe.execute()

                current_count = results[1]
                if current_count >= max_requests:
                    # Fetch oldest timestamp in current window to calculate retry_after
                    oldest_items = await client.zrange(redis_key, 0, 0, withscores=True)
                    retry_after = window_seconds
                    if oldest_items:
                        oldest_ts = oldest_items[0][1]
                        retry_after = max(1, int(window_seconds - (now - oldest_ts)))

                    return {
                        "allowed": False,
                        "retry_after_seconds": retry_after,
                        "message": f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    }

                return {"allowed": True, "retry_after_seconds": 0}
            except Exception as e:
                logger.warning(f"Redis check error ({e}); using memory fallback.")

        # In-Memory Fallback
        bucket = cls._in_memory_buckets.setdefault(key, [])
        # Prune old timestamps
        threshold = now - window_seconds
        cls._in_memory_buckets[key] = [ts for ts in bucket if ts > threshold]

        if len(cls._in_memory_buckets[key]) >= max_requests:
            oldest = cls._in_memory_buckets[key][0]
            retry_after = max(1, int(window_seconds - (now - oldest)))
            return {
                "allowed": False,
                "retry_after_seconds": retry_after,
                "message": f"Rate limit exceeded. Try again in {retry_after} seconds.",
            }

        cls._in_memory_buckets[key].append(now)
        return {"allowed": True, "retry_after_seconds": 0}

    @classmethod
    async def check_login(cls, email: str) -> dict[str, Any]:
        return await cls.check(f"login:{email.lower()}", max_requests=5, window_seconds=60)

    @classmethod
    async def check_register(cls, ip: str) -> dict[str, Any]:
        return await cls.check(f"register:{ip}", max_requests=5, window_seconds=300)

    @classmethod
    async def check_file_upload(cls, user_id: str) -> dict[str, Any]:
        return await cls.check(f"upload:{user_id}", max_requests=10, window_seconds=300)

    @classmethod
    async def check_instant_stats(cls, user_id: str) -> dict[str, Any]:
        return await cls.check(f"instant:{user_id}", max_requests=60, window_seconds=60)

    @classmethod
    async def check_chat(cls, user_id: str) -> dict[str, Any]:
        return await cls.check(f"chat:{user_id}", max_requests=30, window_seconds=60)
