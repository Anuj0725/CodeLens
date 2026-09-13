import json
import hashlib
import logging
import redis.asyncio as redis
from codelens.config import settings

logger = logging.getLogger(__name__)


class ResponseCache:
    """Async Redis cache for query responses. Degrades gracefully if Redis is unavailable."""

    def __init__(self):
        self._client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )

    async def get(self, query: str) -> dict | None:
        """Look up cached response by query hash. Returns None if Redis is down."""
        try:
            key = self._hash_query(query)
            data = await self._client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning(f"Redis cache read failed (degrading gracefully): {e}")
            return None

    async def set(self, query: str, response: dict, ttl: int | None = None) -> None:
        """Cache a response with TTL. Silently skips if Redis is down."""
        try:
            if ttl is None:
                ttl = settings.cache_ttl_seconds
            key = self._hash_query(query)
            await self._client.set(key, json.dumps(response), ex=ttl)
        except Exception as e:
            logger.warning(f"Redis cache write failed (degrading gracefully): {e}")

    async def close(self) -> None:
        """Close Redis connection."""
        try:
            await self._client.aclose()
        except Exception:
            pass

    @staticmethod
    def _hash_query(query: str) -> str:
        """Normalize and hash query for cache key."""
        normalized = query.strip().lower()
        return f"codelens:cache:{hashlib.sha256(normalized.encode()).hexdigest()}"
