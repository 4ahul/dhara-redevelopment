import json
import functools
import logging
from typing import Any, Callable, Optional
from datetime import timedelta

logger = logging.getLogger(__name__)

def redis_cache(
    redis_client_getter: Callable[[], Any],
    prefix: str,
    ttl: int = 600,
    key_builder: Optional[Callable] = None
):
    """
    Decorator to cache function results in Redis.
    Args:
        redis_client_getter: Function that returns a redis client instance.
        prefix: Cache key prefix.
        ttl: Time to live in seconds.
        key_builder: Optional function to build a custom key from args.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            redis = redis_client_getter()
            if not redis:
                return await func(*args, **kwargs)

            # Build cache key
            if key_builder:
                cache_key = f"{prefix}:{key_builder(*args, **kwargs)}"
            else:
                # Default key: prefix + stringified args
                args_str = f"{args}:{kwargs}"
                cache_key = f"{prefix}:{hash(args_str)}"

            try:
                cached_val = redis.get(cache_key)
                if cached_val:
                    logger.debug(f"Cache HIT: {cache_key}")
                    return json.loads(cached_val)
            except Exception as e:
                logger.warning(f"Cache retrieval failed: {e}")

            # Execute and store
            result = await func(*args, **kwargs)
            
            if result and not (isinstance(result, dict) and result.get("error")):
                try:
                    redis.setex(cache_key, ttl, json.dumps(result))
                    logger.debug(f"Cache STORE: {cache_key}")
                except Exception as e:
                    logger.warning(f"Cache storage failed: {e}")

            return result
        return wrapper
    return decorator
