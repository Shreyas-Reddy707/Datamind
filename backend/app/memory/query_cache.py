"""DataMind v2 Query Cache.

Redis-backed LRU caching with memory fallback, scoped to (user_id, user_file_id, query_hash).
Only caches Tier 1 (<25ms) and Tier 2 (<3s) deterministic and quick responses.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("datamind.memory.query_cache")


class QueryCache:
    """Multi-tier cache using Redis with local in-memory fallback."""

    def __init__(self, max_memory_entries: int = 200, ttl_seconds: int = 3600):
        self.ttl = ttl_seconds
        self.max_memory_entries = max_memory_entries
        self._memory_cache: dict[str, dict[str, Any]] = {}
        self._redis_client: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis | None:
        if self._redis_client is None:
            try:
                self._redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=2,
                )
                await self._redis_client.ping()
            except Exception as e:
                logger.debug("Redis cache unavailable (%s), using in-memory fallback", e)
                self._redis_client = None
        return self._redis_client

    @staticmethod
    def compute_key(user_id: uuid.UUID, user_file_id: uuid.UUID, query: str) -> str:
        """Normalized SHA256 key scoped to user and dataset."""
        norm_q = query.lower().strip()
        norm_q = re.sub(r"\s+", " ", norm_q)
        norm_q = re.sub(r"[^\w\s]", "", norm_q)
        raw_key = f"{user_id}:{user_file_id}:{norm_q}"
        digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return f"dm:qc:{digest}"

    async def get(
        self, user_id: uuid.UUID, user_file_id: uuid.UUID, query: str
    ) -> dict[str, Any] | None:
        """Retrieve cached response if within TTL."""
        key = self.compute_key(user_id, user_file_id, query)

        # 1. Try Redis
        client = await self._get_redis()
        if client:
            try:
                val = await client.get(key)
                if val:
                    return json.loads(val)
            except Exception as e:
                logger.debug("Redis get error: %s", e)

        # 2. In-memory fallback
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if time.time() - entry["created_at"] < self.ttl:
                return entry["payload"]
            del self._memory_cache[key]

        return None

    async def set(
        self,
        user_id: uuid.UUID,
        user_file_id: uuid.UUID,
        query: str,
        payload: dict[str, Any],
        tier: int,
    ) -> None:
        """Cache response for Tier 1 or Tier 2. Tier 3 is non-cacheable by design."""
        if tier > 2:
            return

        key = self.compute_key(user_id, user_file_id, query)
        val_str = json.dumps(payload)

        # 1. Try Redis
        client = await self._get_redis()
        if client:
            try:
                await client.set(key, val_str, ex=self.ttl)
                return
            except Exception as e:
                logger.debug("Redis set error: %s", e)

        # 2. In-memory fallback with LRU eviction
        if len(self._memory_cache) >= self.max_memory_entries:
            oldest_key = min(self._memory_cache.keys(), key=lambda k: self._memory_cache[k]["created_at"])
            del self._memory_cache[oldest_key]

        self._memory_cache[key] = {
            "created_at": time.time(),
            "payload": payload,
        }


query_cache = QueryCache()
