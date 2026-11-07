"""
Query Cache for DataMind v4.0.
In-memory LRU cache for Tier 1 and Tier 2 responses.
"""

import time
import hashlib
import re
from typing import Optional, Any, Dict

class QueryCache:
    """
    In-memory LRU cache for chatbot responses.
    Not persisted across app restarts (intentional to ensure data consistency).
    """

    def __init__(self, max_size: int = 50, ttl_seconds: int = 3600):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds

    def _make_key(self, user_id: int, file_id: int, query: str) -> str:
        """
        Creates a normalized hash key for the cache.
        """
        # Normalize: lower, strip, collapse whitespace, remove punctuation
        normalized = query.lower().strip()
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = re.sub(r'[^\w\s]', '', normalized)
        
        raw_key = f"{user_id}:{file_id}:{normalized}"
        return hashlib.md5(raw_key.encode()).hexdigest()

    def get(self, user_id: int, file_id: int, query: str) -> Optional[str]:
        """
        Retrieve a cached response if valid and not expired.
        """
        key = self._make_key(user_id, file_id, query)
        if key in self._cache:
            entry = self._cache[key]
            # Check TTL
            if time.time() - entry["timestamp"] < self._ttl_seconds:
                entry["hit_count"] += 1
                # Update timestamp to maintain LRU property on access if desired, 
                # but instruction just says LRU eviction. We'll update for LRU.
                entry["last_accessed"] = time.time()
                return entry["response"]
            else:
                # Expired
                del self._cache[key]
        return None

    def set(self, user_id: int, file_id: int, query: str, response: str, tier: int):
        """
        Cache a response for Tiers 1 and 2. Tier 3 is never cached.
        """
        if tier == 3:
            return

        # Evict oldest by last_accessed if full
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k].get("last_accessed", self._cache[k]["timestamp"]))
            del self._cache[oldest_key]

        key = self._make_key(user_id, file_id, query)
        now = time.time()
        self._cache[key] = {
            "response": response,
            "tier": tier,
            "timestamp": now,
            "last_accessed": now,
            "hit_count": 0,
            "user_id": user_id,
            "file_id": file_id
        }

    def invalidate_file(self, user_id: int, file_id: int):
        """
        Clears all cached queries for a specific user and file combo.
        Called when a file is re-uploaded or modified.
        """
        keys_to_del = [
            k for k, v in self._cache.items() 
            if v["user_id"] == user_id and v["file_id"] == file_id
        ]
        for k in keys_to_del:
            del self._cache[k]
