import time
import json
import logging
from typing import Any, Optional
import redis.asyncio as aioredis
from app.config import settings

logger = logging.getLogger("api.cache")


class CacheEntry:
    def __init__(self, value: Any, expires_at: float):
        self.value = value
        self.expires_at = expires_at

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class CacheService:
    """Hybrid Caching Layer: Distributed Redis Cluster/Instance with in-memory TTL fallback."""

    def __init__(self):
        self._memory_store: dict[str, CacheEntry] = {}
        self._redis_client: Optional[aioredis.Redis] = None

    async def init_redis(self) -> None:
        if settings.USE_REDIS_CACHE:
            try:
                self._redis_client = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                )
                await self._redis_client.ping()
                logger.info("Connected to distributed Redis cache at %s", settings.REDIS_URL)
            except Exception as e:
                logger.warning("Redis connection failed (%s); operating on in-memory cache fallback.", e)
                self._redis_client = None

    async def close_redis(self) -> None:
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None

    async def get(self, key: str) -> Optional[Any]:
        # 1. Distributed Redis Check
        if self._redis_client:
            try:
                raw = await self._redis_client.get(key)
                if raw:
                    return json.loads(raw)
            except Exception as e:
                logger.warning("Redis GET error (%s); falling back to memory.", e)

        # 2. In-Memory Store Check
        entry = self._memory_store.get(key)
        if not entry:
            return None
        if entry.is_expired():
            del self._memory_store[key]
            return None
        return entry.value

    async def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        # In-Memory Cache Set
        self._memory_store[key] = CacheEntry(
            value=value,
            expires_at=time.time() + ttl_seconds,
        )

        # Distributed Redis Cache Set
        if self._redis_client:
            try:
                payload = value
                if hasattr(value, "model_dump_json"):
                    serialized = value.model_dump_json()
                elif hasattr(value, "model_dump"):
                    serialized = json.dumps(value.model_dump(), default=str)
                else:
                    serialized = json.dumps(value, default=str)
                await self._redis_client.setex(key, ttl_seconds, serialized)
            except Exception as e:
                logger.warning("Redis SET error (%s).", e)

    async def delete(self, key: str) -> None:
        self._memory_store.pop(key, None)
        if self._redis_client:
            try:
                await self._redis_client.delete(key)
            except Exception as e:
                logger.warning("Redis DELETE error (%s).", e)

    async def delete_prefix(self, prefix: str) -> int:
        """Invalidate all cache entries matching a prefix."""
        # Purge memory keys
        keys_to_del = [k for k in self._memory_store if k.startswith(prefix)]
        for k in keys_to_del:
            del self._memory_store[k]

        # Purge Redis keys
        if self._redis_client:
            try:
                cursor = 0
                while True:
                    cursor, keys = await self._redis_client.scan(cursor=cursor, match=f"{prefix}*", count=100)
                    if keys:
                        await self._redis_client.delete(*keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.warning("Redis prefix delete error (%s).", e)

        return len(keys_to_del)

    async def clear(self) -> None:
        self._memory_store.clear()
        if self._redis_client:
            try:
                await self._redis_client.flushdb()
            except Exception as e:
                logger.warning("Redis flush error (%s).", e)


cache_service = CacheService()
