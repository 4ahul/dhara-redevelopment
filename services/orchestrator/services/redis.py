"""
Dhara AI — Redis Session Service
Caches sessions and user profiles in Redis.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

import redis
from arq import create_pool
from arq.connections import RedisSettings

from services.orchestrator.core.config import settings

logger = logging.getLogger(__name__)

redis_client: redis.Redis | None = None
arq_pool: Any = None


async def init_redis():
    """Initialize Redis connection and Arq pool."""
    global redis_client, arq_pool
    try:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        redis_client.ping()
        logger.info("Redis connected")

        # Initialize Arq pool
        arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        logger.info("Arq task pool initialized")
    except Exception as e:
        logger.warning("Redis connection failed: %s — using in-memory fallback.", e)
        redis_client = None
        arq_pool = None


async def close_redis():
    """Close connections."""
    global arq_pool
    if arq_pool:
        await arq_pool.close()
        logger.info("Arq task pool closed")


def get_redis() -> redis.Redis | None:
    return redis_client


def get_arq():
    return arq_pool


def save_session(session_id: str, user_id: str, data: dict) -> bool:
    if not redis_client:
        return False
    try:
        key = f"session:{user_id}:{session_id}"
        data["session_id"] = session_id
        data["user_id"] = user_id
        now_iso = datetime.now(UTC).isoformat()
        data["created_at"] = data.get("created_at", now_iso)
        data["updated_at"] = now_iso
        redis_client.hset(
            key,
            mapping={
                "session_id": session_id,
                "user_id": user_id,
                "data": json.dumps(data),
                "created_at": data["created_at"],
                "updated_at": data["updated_at"],
            },
        )
        redis_client.expire(key, 86400 * 30)
        return True
    except Exception as e:
        logger.error("Failed to save session: %s", e)
        return False


def get_session(session_id: str, user_id: str) -> dict | None:
    if not redis_client:
        return None
    try:
        data = redis_client.hgetall(f"session:{user_id}:{session_id}")
        if data and data.get("data"):
            return json.loads(data["data"])
    except Exception as e:
        logger.error("Failed to get session: %s", e)
    return None


def get_user_sessions(user_id: str) -> list:
    if not redis_client:
        return []
    try:
        keys = redis_client.keys(f"session:{user_id}:*")
        sessions = []
        for key in keys:
            data = redis_client.hgetall(key)
            if data:
                sessions.append(
                    {
                        "session_id": data.get("session_id"),
                        "data": json.loads(data.get("data", "{}")),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                    }
                )
        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
    except Exception as e:
        logger.error("Failed to get user sessions: %s", e)
    return []


def delete_session(session_id: str, user_id: str) -> bool:
    if not redis_client:
        return False
    try:
        return redis_client.delete(f"session:{user_id}:{session_id}") > 0
    except Exception as e:
        logger.error("Failed to delete session: %s", e)
    return False


def save_user_profile(user_id: str, data: dict) -> bool:
    if not redis_client:
        return False
    try:
        redis_client.hset(f"user:{user_id}", mapping=data)
        return True
    except Exception as e:
        logger.error("Failed to save user profile: %s", e)
    return False


def get_user_profile(user_id: str) -> dict:
    if not redis_client:
        return {}
    try:
        return redis_client.hgetall(f"user:{user_id}")
    except Exception as e:
        logger.error("Failed to get user profile: %s", e)
    return {}


def update_session_report(session_id: str, user_id: str, report_path: str) -> bool:
    if not redis_client:
        return False
    try:
        key = f"session:{user_id}:{session_id}"
        redis_client.hset(key, "report_path", report_path)
        redis_client.hset(key, "updated_at", datetime.now(UTC).isoformat())
        return True
    except Exception as e:
        logger.error("Failed to update session report: %s", e)
    return False
