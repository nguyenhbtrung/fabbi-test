import hashlib

import redis.asyncio as aioredis

from app.core.config import settings


class RedisClient:
    def __init__(self):
        self._redis = None

    async def initialize(self):
        self._redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )

    async def close(self):
        if self._redis:
            await self._redis.close()

    @property
    def client(self):
        return self._redis

    async def get(self, key: str) -> str | None:
        return await self._redis.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        await self._redis.set(key, value, ex=ex)

    async def delete(self, key: str):
        await self._redis.delete(key)

    async def delete_pattern(self, pattern: str):
        keys = []
        async for key in self._redis.scan_iter(match=pattern):
            keys.append(key)
        if keys:
            await self._redis.delete(*keys)

    async def exists(self, key: str) -> bool:
        return await self._redis.exists(key)

    async def blacklist_token(self, token: str, ttl_seconds: int = 60 * 60 * 24 * 7):
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        await self._redis.set(f"blacklisted_token:{token_hash}", "1", ex=ttl_seconds)

    async def is_blacklisted(self, token: str) -> bool:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return bool(await self._redis.get(f"blacklisted_token:{token_hash}"))


redis_client = RedisClient()
