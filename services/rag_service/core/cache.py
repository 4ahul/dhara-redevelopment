import redis
import os
import json
from typing import Optional, Any


class RedisCache:
    def __init__(self):
        self.redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            self.client.ping()
            self.available = True
        except Exception as e:
            print(f"Redis not available: {e}")
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
            print(f"Redis get error: {e}")
        return None

    def set(self, key: str, value: Any, expire: int = 3600):
        if not self.available:
            return False
        try:
            self.client.setex(key, expire, json.dumps(value))
            return True
        except Exception as e:
            print(f"Redis set error: {e}")
            return False

    def delete(self, key: str):
        if not self.available:
            return
        try:
            self.client.delete(key)
        except Exception as e:
            print(f"Redis delete error: {e}")

    def clear_pattern(self, pattern: str):
        if not self.available:
            return
        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
        except Exception as e:
            print(f"Redis clear error: {e}")


cache = RedisCache()
