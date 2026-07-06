"""Redis cache service — optional, degrades gracefully without Redis."""

import json
import logging
from typing import Optional
from app.config import get_settings

log = logging.getLogger("realty")
settings = get_settings()

_redis_client = None


def get_redis():
    """Get Redis client. Returns None if Redis unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    if not getattr(settings, 'REDIS_URL', ''):
        return None

    try:
        import redis.asyncio as aioredis
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
        )
        return _redis_client
    except Exception as e:
        log.warning(f"Redis unavailable: {e}")
        return None


class CacheService:
    """Simple Redis cache with TTL. No-op if Redis unavailable."""

    def __init__(self, prefix: str = "nedvig"):
        self.prefix = prefix
        self._redis = None

    @property
    def redis(self):
        if self._redis is None:
            self._redis = get_redis()
        return self._redis

    async def get(self, key: str) -> Optional[dict]:
        """Get cached value. Returns None if miss or unavailable."""
        if self.redis is None:
            return None
        try:
            data = await self.redis.get(f"{self.prefix}:{key}")
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    async def set(self, key: str, value: dict, ttl: int = 300):
        """Set cached value with TTL (seconds)."""
        if self.redis is None:
            return
        try:
            await self.redis.set(
                f"{self.prefix}:{key}",
                json.dumps(value, default=str),
                ex=ttl,
            )
        except Exception:
            pass

    async def delete(self, key: str):
        """Delete a cached key."""
        if self.redis is None:
            return
        try:
            await self.redis.delete(f"{self.prefix}:{key}")
        except Exception:
            pass

    async def invalidate_pattern(self, pattern: str):
        """Delete all keys matching pattern."""
        if self.redis is None:
            return
        try:
            keys = []
            async for key in self.redis.scan_iter(f"{self.prefix}:{pattern}"):
                keys.append(key)
            if keys:
                await self.redis.delete(*keys)
        except Exception:
            pass

    async def ping(self) -> bool:
        """Check if Redis is available."""
        if self.redis is None:
            return False
        try:
            return await self.redis.ping()
        except Exception:
            return False


# Singleton instances
analytics_cache = CacheService(prefix="nedvig:analytics")
search_cache = CacheService(prefix="nedvig:search")
stats_cache = CacheService(prefix="nedvig:stats")
