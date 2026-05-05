import functools
import json
import logging
import os
from collections.abc import Callable
from typing import Any, Optional

import redis

logger = logging.getLogger(__name__)


class RedisCache:
    """Centralized Redis cache management."""

    _instance: Optional["RedisCache"] = None
    _client: redis.Redis | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            url = os.getenv("REDIS_URL", "redis://localhost:6379")
            try:
                cls._client = redis.from_url(url, decode_responses=True)
                cls._client.ping()
                logger.info(f"Connected to Redis at {url}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis at {url}: {e}")
                cls._client = None
        return cls._instance

    @property
    def client(self) -> redis.Redis | None:
        return self._client

    def get(self, key: str) -> Any | None:
        if not self._client:
            return None
        try:
            val = self._client.get(key)
            return json.loads(val) if val else None
        except Exception as e:
            logger.warning(f"Redis GET failed for {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 3600):
        if not self._client:
            return
        try:
            self._client.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.warning(f"Redis SET failed for {key}: {e}")

    def delete(self, key: str):
        if not self._client:
            return
        try:
            self._client.delete(key)
        except Exception as e:
            logger.warning(f"Redis DELETE failed for {key}: {e}")


def redis_cache(prefix: str, ttl: int = 3600, key_builder: Callable | None = None):
    """
    Decorator to cache function results in Redis.
    Automatically uses the global RedisCache instance.
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache = RedisCache()
            if not cache.client:
                return await func(*args, **kwargs)

            # Build cache key
            k_part = key_builder(*args, **kwargs) if key_builder else f"{args}:{kwargs}"

            cache_key = f"{prefix}:{k_part}"

            cached_val = cache.get(cache_key)
            if cached_val:
                logger.debug(f"Cache HIT: {cache_key}")
                return cached_val

            # Execute and store
            result = await func(*args, **kwargs)

            # Don't cache errors
            if result and not (isinstance(result, dict) and result.get("error")):
                cache.set(cache_key, result, ttl)
                logger.debug(f"Cache STORE: {cache_key}")

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache = RedisCache()
            if not cache.client:
                return func(*args, **kwargs)

            k_part = key_builder(*args, **kwargs) if key_builder else f"{args}:{kwargs}"

            cache_key = f"{prefix}:{k_part}"

            cached_val = cache.get(cache_key)
            if cached_val:
                return cached_val

            result = func(*args, **kwargs)
            if result and not (isinstance(result, dict) and result.get("error")):
                cache.set(cache_key, result, ttl)

            return result

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
