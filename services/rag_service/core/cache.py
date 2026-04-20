import os
import json
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self):
        self.redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        try:
            import redis
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            self.client.ping()
            self.available = True
        except ImportError:
            logger.warning("Redis not available: package not installed")
            self.client = None
            self.available = False
        except Exception as e:
            logger.warning(f"Redis not available: {e}")
            self.client = None
            self.available = False

    def get(self, key: str) -> Optional[Any]:
        if not self.available:
            return None
        try:
            data = self.client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Redis get error: {e}", exc_info=True)
        return None

    def set(self, key: str, value: Any, expire: int = 3600):
        if not self.available:
            return False
        try:
            self.client.setex(key, expire, json.dumps(value))
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}", exc_info=True)
            return False

    def delete(self, key: str):
        if not self.available:
            return
        try:
            self.client.delete(key)
        except Exception as e:
            logger.error(f"Redis delete error: {e}", exc_info=True)

    def clear_pattern(self, pattern: str):
        if not self.available:
            return
        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis clear error: {e}", exc_info=True)


# Global cache instance
cache = RedisCache()
